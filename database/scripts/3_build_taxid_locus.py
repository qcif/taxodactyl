"""Build TaxID-level locus counts from the Step 5 and 6 DuckDB tables.

TaxonKit runs locally. Taxonomy output is streamed to a temporary TSV file,
loaded into DuckDB and removed after the build. No persistent cache is used.
"""

import argparse
import csv
import itertools
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb


RANKS = (
    "domain", "kingdom", "phylum", "class",
    "order", "family", "genus", "species",
)
TAXONOMY_FIELDS = [
    "taxid", "resolved_taxid", "resolution_status",
    *(f"rank_{rank}" for rank in RANKS),
]
STATUS_VALUES = ("current", "merged", "deleted", "not_found")


def parse_arguments():
    """Read database, taxonomy and build-provenance arguments."""
    parser = argparse.ArgumentParser(
        description="Build taxid_locus and build_info from Steps 5 and 6."
    )
    parser.add_argument("--db", required=True, help="Existing DuckDB file")
    parser.add_argument(
        "--extraction-date", help="YYYY-MM-DD of metadata extraction"
    )
    parser.add_argument(
        "--core-nt-version", help="Database description from blastdbcmd -info"
    )
    parser.add_argument(
        "--taxonkit", default="taxonkit", help="Local TaxonKit executable"
    )
    parser.add_argument(
        "--taxdb", default=str(Path.home() / ".taxonkit"),
        help="Directory containing NCBI taxonomy dump files",
    )
    parser.add_argument(
        "--batch-size", type=int, default=100000,
        help="Number of source TaxIDs fetched from DuckDB at a time",
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="Validate Steps 5 and 6 inputs without writing anything",
    )
    return parser.parse_args()


def validate_arguments(args):
    """Validate input paths without changing the system Python environment."""
    database = Path(args.db).expanduser().resolve()
    if not database.is_file():
        raise FileNotFoundError(f"DuckDB file not found: {database}")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be positive")
    if args.check_only:
        return database

    if not args.extraction_date or not (args.core_nt_version or "").strip():
        raise ValueError(
            "--extraction-date and --core-nt-version are required"
        )
    parsed = datetime.strptime(args.extraction_date, "%Y-%m-%d")
    if parsed.strftime("%Y-%m-%d") != args.extraction_date:
        raise ValueError("--extraction-date must use YYYY-MM-DD")

    executable = Path(args.taxonkit).expanduser()
    if executable.is_file():
        args.taxonkit = str(executable.resolve())
    else:
        resolved = shutil.which(args.taxonkit)
        if resolved is None:
            raise FileNotFoundError(
                f"TaxonKit executable not found: {args.taxonkit}"
            )
        args.taxonkit = resolved

    args.taxdb = str(Path(args.taxdb).expanduser().resolve())
    taxonomy = Path(args.taxdb)
    for filename in ("nodes.dmp", "names.dmp", "merged.dmp", "delnodes.dmp"):
        if not (taxonomy / filename).is_file():
            raise FileNotFoundError(
                f"Missing taxonomy file: {taxonomy / filename}"
            )
    return database


def permanent_locus_mapping():
    """Read permanent active and retired IDs from the Step 6 registry."""
    path = Path(__file__).resolve().parent / "config" / "locus_ids.json"
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)

    active = registry.get("active")
    retired = registry.get("retired", {})
    next_id = registry.get("next_id")
    if (
        not isinstance(active, dict) or not active
        or not isinstance(retired, dict)
    ):
        raise ValueError("Invalid active/retired locus registry")
    if set(active) & set(retired):
        raise ValueError("Active and retired locus names overlap")
    used_ids = list(active.values()) + list(retired.values())
    if any(type(value) is not int or value < 1 for value in used_ids):
        raise ValueError("Locus IDs must be positive integers")
    if len(used_ids) != len(set(used_ids)):
        raise ValueError("Duplicate permanent locus IDs")
    if type(next_id) is not int or next_id <= max(used_ids, default=0):
        raise ValueError("Invalid next_id in permanent locus registry")
    return active, retired


def validate_database(database):
    """Verify source tables, locus IDs and sparse classifications."""
    active, retired = permanent_locus_mapping()
    db = duckdb.connect(str(database), read_only=True)
    try:
        tables = {name for (name,) in db.execute("SHOW TABLES").fetchall()}
        if not {"records", "loci", "record_locus"}.issubset(tables):
            raise ValueError("Steps 5 and 6 tables are required")
        pairs = db.execute(
            "SELECT DISTINCT name, locus_id FROM loci"
        ).fetchall()
        if len(pairs) != len(active) or dict(pairs) != active:
            raise ValueError(
                "Database locus IDs differ from config/locus_ids.json"
            )

        records, taxids, null_taxids = db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT taxid), "
            "COUNT(*) FILTER (WHERE taxid IS NULL) FROM records"
        ).fetchone()
        if not records or not taxids or null_taxids:
            raise ValueError("records must contain non-NULL TaxIDs")
        present, unknown, invalid = db.execute(
            "SELECT COUNT(*) FILTER (WHERE status='present'), "
            "COUNT(*) FILTER (WHERE status='unknown'), "
            "COUNT(*) FILTER (WHERE status IS NULL OR "
            "status NOT IN ('present','unknown')) FROM record_locus"
        ).fetchone()
        if invalid or present + unknown > records * len(active):
            raise ValueError("Invalid sparse record_locus statuses or counts")

        orphan = db.execute(
            "SELECT 1 FROM record_locus rl WHERE NOT EXISTS "
            "(SELECT 1 FROM records r WHERE r.accession=rl.accession) LIMIT 1"
        ).fetchone()
        if orphan:
            raise ValueError("record_locus refers to an unknown accession")
        duplicate = db.execute(
            "SELECT 1 FROM record_locus GROUP BY accession, locus_id "
            "HAVING COUNT(*) > 1 LIMIT 1"
        ).fetchone()
        if duplicate:
            raise ValueError("Duplicate accession/locus pair in record_locus")
        unknown_locus = db.execute(
            "SELECT 1 FROM record_locus rl WHERE NOT EXISTS "
            "(SELECT 1 FROM loci l WHERE l.locus_id=rl.locus_id) LIMIT 1"
        ).fetchone()
        if unknown_locus:
            raise ValueError("record_locus refers to an unknown locus ID")

        return {
            "records": records,
            "taxids": taxids,
            "present": present,
            "unknown": unknown,
            "loci_rows": db.execute("SELECT COUNT(*) FROM loci").fetchone()[0],
            "active_ids": sorted(active.values()),
            "retired_ids": sorted(retired.values()),
        }
    finally:
        db.close()


def taxonomy_environment(args):
    """Report the local TaxonKit version and taxonomy dump timestamp."""
    result = subprocess.run(
        [args.taxonkit, "version"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True,
    )
    version = result.stdout.strip() or result.stderr.strip()
    if not version:
        raise ValueError("TaxonKit version could not be determined")
    timestamp = (Path(args.taxdb) / "nodes.dmp").stat().st_mtime
    label = "nodes.dmp mtime " + datetime.fromtimestamp(
        timestamp, timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return version, label


def export_taxids(database, destination, batch_size):
    """Export sorted, distinct source TaxIDs without loading them into RAM."""
    count = 0
    db = duckdb.connect(str(database), read_only=True)
    try:
        cursor = db.execute(
            "SELECT DISTINCT taxid FROM records "
            "WHERE taxid IS NOT NULL ORDER BY taxid"
        )
        with destination.open("w", encoding="utf-8", newline="\n") as out:
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                for (taxid,) in rows:
                    out.write(f"{int(taxid)}\n")
                count += len(rows)
    finally:
        db.close()
    return count


def parse_taxonomy_row(expected_taxid, line):
    """Convert one TaxonKit response to the taxonomy TSV schema."""
    fields = line.rstrip("\r\n").split("\t")
    if len(fields) < 2 or fields[0] != expected_taxid:
        raise ValueError(
            f"Misaligned TaxonKit response for TaxID {expected_taxid}"
        )

    code = int(fields[1])
    resolved_taxid = ""
    ranks = {rank: "" for rank in RANKS}
    if code > 0:
        resolved_taxid = str(code)
        status = "current" if code == int(expected_taxid) else "merged"
        if len(fields) < 5:
            raise ValueError(
                f"Missing lineage information for TaxID {expected_taxid}"
            )
        names = fields[2].split(";") if fields[2] else []
        rank_names = fields[4].split(";") if fields[4] else []
        if len(names) != len(rank_names):
            raise ValueError(
                f"Lineage/rank mismatch for TaxID {expected_taxid}"
            )
        for name, rank in zip(names, rank_names):
            if rank == "superkingdom" and not ranks["domain"]:
                ranks["domain"] = name
            elif rank in ranks:
                ranks[rank] = name
    elif code == 0:
        status = "deleted"
    elif code == -1:
        status = "not_found"
    else:
        raise ValueError(
            f"Unexpected TaxonKit code {code} for {expected_taxid}"
        )

    return [
        expected_taxid, resolved_taxid, status,
        *(ranks[rank] for rank in RANKS),
    ]


def resolve_taxonomy(args, input_file, output_file, expected_rows):
    """Stream one TaxonKit process into a temporary, validated TSV file."""
    command = [
        args.taxonkit, "lineage", "--data-dir", args.taxdb, "-c", "-t", "-R"
    ]
    errors_file = output_file.with_suffix(".stderr.log")
    with input_file.open("r", encoding="utf-8") as taxids, \
            input_file.open("r", encoding="utf-8") as stdin_file, \
            output_file.open("w", encoding="utf-8", newline="") as out, \
            errors_file.open("w", encoding="utf-8") as errors:
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        writer.writerow(TAXONOMY_FIELDS)
        process = subprocess.Popen(
            command, stdin=stdin_file, stdout=subprocess.PIPE, stderr=errors,
            text=True, encoding="utf-8", errors="replace",
        )
        count = 0
        try:
            with process.stdout:
                for expected, line in itertools.zip_longest(
                    taxids, process.stdout
                ):
                    if expected is None or line is None:
                        raise ValueError(
                            "TaxonKit output count differs from source TaxIDs"
                        )
                    writer.writerow(parse_taxonomy_row(expected.strip(), line))
                    count += 1
            returncode = process.wait()
            if returncode:
                raise RuntimeError(
                    f"TaxonKit returned exit code {returncode}; "
                    f"see {errors_file}"
                )
            if count != expected_rows:
                raise ValueError(
                    f"Taxonomy row count {count} != {expected_rows}"
                )
        except Exception:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
    return count


def sql_quote(value):
    """Quote a path literal used in DuckDB SQL."""
    return "'" + str(value).replace("'", "''") + "'"


def validate_rollup(db, stats):
    """Check exact TaxID counts and every active/retired locus column."""
    rows, unique, total = db.execute(
        "SELECT COUNT(*), COUNT(DISTINCT taxid), "
        "COALESCE(SUM(n_records), 0) FROM taxid_locus"
    ).fetchone()
    if rows != stats["taxids"] or unique != rows or total != stats["records"]:
        raise ValueError("TaxID row count, uniqueness or record totals differ")

    present_counts = dict(db.execute(
        "SELECT locus_id, COUNT(*) FROM record_locus "
        "WHERE status='present' GROUP BY locus_id"
    ).fetchall())
    all_ids = stats["active_ids"] + stats["retired_ids"]
    columns = ", ".join(f"COALESCE(SUM(locus_{i}), 0)" for i in all_ids)
    totals = db.execute(f"SELECT {columns} FROM taxid_locus").fetchone()
    for locus_id, count in zip(all_ids, totals):
        if count != present_counts.get(locus_id, 0):
            raise ValueError(f"locus_{locus_id} count does not match source")

    invalid = db.execute(
        "SELECT 1 FROM taxid_locus WHERE " + " OR ".join(
            f"locus_{i} IS NULL OR locus_{i}<0 OR locus_{i}>n_records"
            for i in all_ids
        ) + " LIMIT 1"
    ).fetchone()
    if invalid:
        raise ValueError("Invalid per-TaxID locus counts")
    return rows


def build_tables(database, taxonomy_file, stats, args, versions):
    """Replace both aggregate tables in a single DuckDB transaction."""
    db = duckdb.connect(str(database))
    in_transaction = False
    try:
        db.execute("BEGIN TRANSACTION")
        in_transaction = True
        rank_columns = ", ".join(
            f"NULLIF(rank_{rank}, '') AS rank_{rank}" for rank in RANKS
        )
        db.execute(f"""
            CREATE TEMP TABLE taxonomy_resolution_tmp AS
            SELECT CAST(taxid AS BIGINT) AS taxid,
                   TRY_CAST(NULLIF(resolved_taxid, '') AS BIGINT)
                       AS resolved_taxid,
                   resolution_status,
                   {rank_columns}
            FROM read_csv_auto({sql_quote(taxonomy_file.as_posix())},
                               delim='\\t', header=true, all_varchar=true)
        """)
        row_count, distinct = db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT taxid) "
            "FROM taxonomy_resolution_tmp"
        ).fetchone()
        if row_count != stats["taxids"] or distinct != row_count:
            raise ValueError(
                "Taxonomy rows do not match distinct source TaxIDs"
            )
        missing = db.execute(
            "SELECT 1 FROM (SELECT DISTINCT taxid FROM records) r "
            "LEFT JOIN taxonomy_resolution_tmp t ON r.taxid=t.taxid "
            "WHERE t.taxid IS NULL LIMIT 1"
        ).fetchone()
        if missing:
            raise ValueError(
                "Taxonomy output does not cover all source TaxIDs"
            )

        statuses = dict(db.execute(
            "SELECT resolution_status, COUNT(*) "
            "FROM taxonomy_resolution_tmp GROUP BY resolution_status"
        ).fetchall())
        if set(statuses) - set(STATUS_VALUES):
            raise ValueError("Unexpected taxonomy resolution status")
        if sum(statuses.values()) != stats["taxids"]:
            raise ValueError("Taxonomy status counts do not reconcile")

        active_ids = stats["active_ids"]
        retired_ids = stats["retired_ids"]
        pivot = ", ".join(
            f"SUM(CASE WHEN locus_id={i} THEN n_present ELSE 0 END)"
            f"::BIGINT AS locus_{i}"
            for i in active_ids
        )
        active_columns = [
            f"COALESCE(p.locus_{i}, 0)::BIGINT AS locus_{i}"
            for i in active_ids
        ]
        # Keep retired locus columns so their IDs cannot be reused.
        retired_columns = [f"0::BIGINT AS locus_{i}" for i in retired_ids]
        locus_columns = ", ".join(active_columns + retired_columns)

        db.execute("DROP TABLE IF EXISTS taxid_locus")
        db.execute(f"""
            CREATE TABLE taxid_locus AS
            WITH record_counts AS (
                SELECT taxid, COUNT(*)::BIGINT AS n_records
                FROM records GROUP BY taxid
            ),
            present_long AS (
                SELECT r.taxid, rl.locus_id, COUNT(*)::BIGINT AS n_present
                FROM record_locus rl
                JOIN records r ON r.accession=rl.accession
                WHERE rl.status='present'
                GROUP BY r.taxid, rl.locus_id
            ),
            present_counts AS (
                SELECT taxid, {pivot} FROM present_long GROUP BY taxid
            )
            SELECT c.taxid,
                   t.resolved_taxid,
                   t.resolution_status,
                   {', '.join(f't.rank_{rank}' for rank in RANKS)},
                   c.n_records, {locus_columns}
            FROM record_counts c
            LEFT JOIN taxonomy_resolution_tmp t ON t.taxid=c.taxid
            LEFT JOIN present_counts p ON p.taxid=c.taxid
        """)
        aggregate_rows = validate_rollup(db, stats)
        db.execute(
            "CREATE UNIQUE INDEX idx_taxid_locus_taxid "
            "ON taxid_locus(taxid)"
        )
        db.execute(
            "CREATE INDEX idx_taxid_locus_resolved "
            "ON taxid_locus(resolved_taxid)"
        )
        db.execute(
            "CREATE INDEX idx_taxid_locus_genus ON taxid_locus(rank_genus)"
        )
        db.execute(
            "CREATE INDEX idx_taxid_locus_species "
            "ON taxid_locus(rank_species)"
        )

        sparse_rows = db.execute(
            "SELECT COUNT(*) FROM record_locus"
        ).fetchone()[0]
        absent = (
            stats["records"] * len(active_ids)
            - stats["present"] - stats["unknown"]
        )
        if absent < 0:
            raise ValueError("Negative absent record-locus count")

        db.execute("DROP TABLE IF EXISTS build_info")
        db.execute("""
            CREATE TABLE build_info (
                extraction_date DATE, core_nt_version TEXT,
                taxdump_version TEXT,
                taxonkit_version TEXT, built_at_utc TEXT,
                records_rows BIGINT, loci_rows BIGINT,
                record_locus_rows BIGINT,
                taxid_locus_rows BIGINT, present_count BIGINT,
                unknown_count BIGINT, absent_count BIGINT,
                distinct_taxids BIGINT, taxonomy_current BIGINT,
                taxonomy_merged BIGINT, taxonomy_deleted BIGINT,
                taxonomy_not_found BIGINT
            )
        """)
        db.execute("""
            INSERT INTO build_info VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            args.extraction_date, args.core_nt_version,
            versions[1], versions[0],
            datetime.now(timezone.utc).isoformat(),
            stats["records"], stats["loci_rows"], sparse_rows, aggregate_rows,
            stats["present"], stats["unknown"], absent, stats["taxids"],
            *(statuses.get(value, 0) for value in STATUS_VALUES),
        ])
        if db.execute("SELECT COUNT(*) FROM build_info").fetchone()[0] != 1:
            raise ValueError("build_info must have one row")
        db.execute("COMMIT")
        in_transaction = False
        return aggregate_rows, absent, statuses
    except Exception:
        if in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def main():
    """Validate the source, resolve taxonomy and build the aggregate tables."""
    args = parse_arguments()
    database = validate_arguments(args)
    print("Validating source tables and locus IDs...", flush=True)
    stats = validate_database(database)
    print(
        f"Records: {stats['records']:,} | TaxIDs: {stats['taxids']:,} | "
        f"present: {stats['present']:,} | unknown: {stats['unknown']:,}",
        flush=True,
    )
    if args.check_only:
        print("Input validation complete (read-only mode)", flush=True)
        return

    versions = taxonomy_environment(args)
    with tempfile.TemporaryDirectory(
        prefix="step7_", dir=database.parent
    ) as tmp:
        temporary = Path(tmp)
        input_file = temporary / "taxids.txt"
        taxonomy_file = temporary / "taxonomy.tsv"
        count = export_taxids(database, input_file, args.batch_size)
        if count != stats["taxids"]:
            raise ValueError("Distinct TaxID extraction count mismatch")
        print(f"Resolving {count:,} TaxIDs with TaxonKit...", flush=True)
        resolved = resolve_taxonomy(args, input_file, taxonomy_file, count)
        if resolved != count:
            raise ValueError("Taxonomy resolution count mismatch")
        rows, absent, statuses = build_tables(
            database, taxonomy_file, stats, args, versions
        )
    print(
        "Taxonomy: " + ", ".join(
            f"{status}={statuses.get(status, 0):,}" for status in STATUS_VALUES
        ),
        flush=True,
    )
    print(
        f"Build complete: {rows:,} TaxIDs | "
        f"present={stats['present']:,} | unknown={stats['unknown']:,} | "
        f"absent={absent:,}",
        flush=True,
    )


if __name__ == "__main__":
    main()
