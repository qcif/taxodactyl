# To Build TaxID-level locus counts using the existing DuckDB tables and NCBI taxonomy.

import argparse
import csv
import hashlib
import itertools
import json
import shlex
import shutil
import subprocess
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
STATUS_VALUES = {"current", "merged", "deleted", "not_found"}


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Build taxid_locus and build_info from Steps 5 and 6."
    )
    parser.add_argument("--db", required=True, help="Existing DuckDB file.")
    parser.add_argument("--extraction-date", help="YYYY-MM-DD; required for a build.")
    parser.add_argument("--core-nt-version", help="Exact blastdbcmd -info version/date; required for a build.")
    parser.add_argument("--batch-size", type=int, default=100000)
    parser.add_argument("--mode", choices=("local", "ssh"), default="local",
                        help="Run TaxonKit on this machine (VM), or over SSH.")
    parser.add_argument("--taxonkit", default="taxonkit",
                        help="Local TaxonKit executable or executable path.")
    parser.add_argument("--taxdb", default=str(Path.home() / ".taxonkit"),
                        help="Local taxdump directory (nodes.dmp etc.).")
    parser.add_argument("--ssh-host", help="SSH destination for --mode ssh, e.g. ubuntu@HOST.")
    parser.add_argument("--ssh-key", default=str(Path.home() / ".ssh" / "qcif_ed25519"))
    parser.add_argument("--remote-taxonkit", default="/mnt/data/taxonkit/taxonkit")
    parser.add_argument("--remote-taxdb", default="/mnt/data/taxonkit")
    parser.add_argument("--work-dir", help="Separate persistent directory for resumable cache.")
    parser.add_argument("--check-only", action="store_true",
                        help="Read-only input/ID validation; no SSH, cache or DB writes.")
    return parser.parse_args()


def validate_arguments(args):
    database = Path(args.db).expanduser().resolve()
    if not database.is_file():
        raise FileNotFoundError(f"Existing DuckDB file not found: {database}")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be positive")
    if not args.check_only:
        if not args.extraction_date or not args.core_nt_version or not args.core_nt_version.strip():
            raise ValueError("--extraction-date and --core-nt-version are required for a build")
        parsed = datetime.strptime(args.extraction_date, "%Y-%m-%d")
        if parsed.strftime("%Y-%m-%d") != args.extraction_date:
            raise ValueError("--extraction-date must be formatted YYYY-MM-DD")
        if args.mode == "ssh":
            if not args.ssh_host:
                raise ValueError("--ssh-host is required when --mode ssh")
            if not Path(args.ssh_key).expanduser().is_file():
                raise FileNotFoundError(f"SSH key not found: {args.ssh_key}")
            if shutil.which("ssh") is None:
                raise RuntimeError("ssh executable is not on PATH")
        else:
            binary = Path(args.taxonkit).expanduser()
            if not binary.is_file() and shutil.which(args.taxonkit) is None:
                raise FileNotFoundError(f"TaxonKit executable not found: {args.taxonkit}")
            if not Path(args.taxdb).expanduser().is_dir():
                raise FileNotFoundError(f"Taxdump directory not found: {args.taxdb}")
    return database


def permanent_locus_mapping():
    path = Path(__file__).resolve().parent / "config" / "locus_ids.json"
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    active = registry.get("active")
    retired = registry.get("retired", {})
    next_id = registry.get("next_id")
    if not isinstance(active, dict) or not isinstance(retired, dict):
        raise ValueError("Invalid permanent locus ID registry")
    if set(active).intersection(retired):
        raise ValueError("Active and retired locus names overlap")
    values = list(active.values()) + list(retired.values())
    if any(type(value) is not int or value < 1 for value in values):
        raise ValueError("Locus IDs must be positive integers")
    if len(set(values)) != len(values):
        raise ValueError("Duplicate permanent locus IDs")
    if type(next_id) is not int or next_id <= max(values, default=0):
        raise ValueError("Invalid next_id in permanent locus registry")
    if sorted(active.values()) != list(range(1, 32)):
        raise ValueError("Phase 1 requires the existing 31 permanent IDs (1 through 31)")
    return active


def validate_database(database):
    expected = permanent_locus_mapping()
    db = duckdb.connect(str(database), read_only=True)
    try:
        tables = {row[0] for row in db.execute("SHOW TABLES").fetchall()}
        if not {"records", "loci", "record_locus"}.issubset(tables):
            raise ValueError("Steps 5/6 tables records, loci, record_locus are required")
        locus_pairs = db.execute("SELECT DISTINCT name, locus_id FROM loci").fetchall()
        actual = dict(locus_pairs)
        if len(locus_pairs) != len(expected) or actual != expected:
            raise ValueError("Database locus names/IDs differ from config/locus_ids.json")
        records, taxids, null_taxids = db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT taxid), "
            "COUNT(*) FILTER (WHERE taxid IS NULL) FROM records"
        ).fetchone()
        if not records or not taxids or null_taxids:
            raise ValueError("records must be non-empty with no NULL taxids")
        present, unknown, bad = db.execute(
            "SELECT COUNT(*) FILTER (WHERE status = 'present'), "
            "COUNT(*) FILTER (WHERE status = 'unknown'), "
            "COUNT(*) FILTER (WHERE status IS NULL OR status NOT IN ('present','unknown')) "
            "FROM record_locus"
        ).fetchone()
        if bad or present + unknown > records * len(expected):
            raise ValueError("Invalid sparse record_locus statuses or counts")
        duplicate = db.execute(
            "SELECT 1 FROM record_locus GROUP BY accession, locus_id "
            "HAVING COUNT(*) > 1 LIMIT 1"
        ).fetchone()
        if duplicate:
            raise ValueError("Duplicate (accession, locus_id) in record_locus")
        unknown_loci = db.execute(
            "SELECT 1 FROM record_locus rl "
            "WHERE NOT EXISTS (SELECT 1 FROM loci l WHERE l.locus_id = rl.locus_id) "
            "LIMIT 1"
        ).fetchone()
        if unknown_loci:
            raise ValueError("record_locus refers to an unknown locus ID")
        return {
            "records": records, "taxids": taxids, "present": present,
            "unknown": unknown, "loci_rows": db.execute("SELECT COUNT(*) FROM loci").fetchone()[0],
            "locus_ids": sorted(expected.values()),
        }
    finally:
        db.close()


def run_remote(args, remote_command):
    proc = subprocess.run(
        ["ssh", "-i", str(Path(args.ssh_key).expanduser()), "-o", "BatchMode=yes",
         args.ssh_host, remote_command],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or f"Remote command failed: {remote_command}")
    return proc.stdout.strip()


def taxonomy_environment(args):
    """Read TaxonKit and taxonomy file metadata for cache validation."""
    filenames = ("nodes.dmp", "names.dmp", "merged.dmp", "delnodes.dmp")
    if args.mode == "ssh":
        tool = shlex.quote(args.remote_taxonkit)
        tool_version = run_remote(args, f"{tool} version")
        signatures = {}
        for filename in filenames:
            target = shlex.quote(args.remote_taxdb.rstrip("/") + "/" + filename)
            signatures[filename] = run_remote(args, f"stat -c '%s:%Y' {target}")
    else:
        binary = str(Path(args.taxonkit).expanduser()) if Path(args.taxonkit).expanduser().is_file() else args.taxonkit
        proc = subprocess.run([binary, "version"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", check=True)
        tool_version = proc.stdout.strip() or proc.stderr.strip()
        signatures = {}
        for filename in filenames:
            target = Path(args.taxdb).expanduser() / filename
            stat = target.stat()
            signatures[filename] = f"{stat.st_size}:{int(stat.st_mtime)}"
    if not tool_version:
        raise ValueError("TaxonKit version could not be determined")
    if any(not signature for signature in signatures.values()):
        raise ValueError("Could not inspect all required taxonomy dump files")
    taxdump_time = int(signatures["nodes.dmp"].split(":")[1])
    dump_label = "nodes.dmp mtime " + datetime.fromtimestamp(taxdump_time, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return tool_version, signatures, dump_label


def taxid_batches(database, cache_dir, batch_size):
    batch_dir = cache_dir / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect(str(database), read_only=True)
    batches = []
    sha = hashlib.sha256()
    count = 0
    try:
        cursor = db.execute(
            "SELECT DISTINCT taxid FROM records WHERE taxid IS NOT NULL ORDER BY taxid"
        )
        number = 0
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            number += 1
            path = batch_dir / f"batch_{number:06d}.taxids.txt"
            with path.open("w", encoding="utf-8", newline="\n") as output:
                for (taxid,) in rows:
                    line = f"{int(taxid)}\n"
                    output.write(line)
                    sha.update(line.encode("utf-8"))
            batches.append((number, path, len(rows)))
            count += len(rows)
    finally:
        db.close()
    return batches, count, sha.hexdigest()


def check_cache(cache_dir, expected):
    manifest = cache_dir / "manifest.json"
    if manifest.exists():
        with manifest.open("r", encoding="utf-8") as file:
            saved = json.load(file)
        if saved != expected:
            raise RuntimeError(
                "Step 7 cache was generated with different inputs or taxonomy. "
                "Use a NEW --work-dir (do not reuse stale taxonomy results)."
            )
    elif any(cache_dir.glob("batches/*.parsed.tsv")):
        raise RuntimeError("Unverified existing parsed cache: use a NEW --work-dir")
    else:
        tmp = manifest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(expected, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(manifest)


def paths_for(input_path):
    prefix = input_path.name.replace(".taxids.txt", "")
    return {
        "raw": input_path.parent / f"{prefix}.raw.tsv",
        "parsed": input_path.parent / f"{prefix}.parsed.tsv",
        "checksum": input_path.parent / f"{prefix}.parsed.sha256",
        "stderr": input_path.parent / f"{prefix}.stderr.log",
    }


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as file:
        for data in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(data)
    return sha.hexdigest()


def verify_parsed(path, input_path, expected_rows):
    with path.open("r", encoding="utf-8", newline="") as target, input_path.open(
        "r", encoding="utf-8"
    ) as source:
        reader = csv.DictReader(target, delimiter="\t")
        if reader.fieldnames != TAXONOMY_FIELDS:
            raise ValueError(f"Invalid taxonomy output header: {path}")
        count = 0
        for expected_id, row in itertools.zip_longest(source, reader):
            if expected_id is None or row is None:
                raise ValueError(f"Truncated or extra cached rows: {path}")
            if row["taxid"] != expected_id.strip():
                raise ValueError(f"Taxonomy IDs do not match input batch: {path}")
            status = row["resolution_status"]
            resolved = row["resolved_taxid"]
            if status not in STATUS_VALUES:
                raise ValueError(f"Unexpected taxonomy status: {status}")
            if status in {"current", "merged"}:
                if not resolved or int(resolved) <= 0:
                    raise ValueError(f"Missing resolved TaxID: {path}")
                if (status == "current") != (resolved == row["taxid"]):
                    raise ValueError(f"Inconsistent current/merged TaxID: {path}")
            elif resolved:
                raise ValueError(f"Deleted/not_found taxid has resolution: {path}")
            count += 1
        if count != expected_rows:
            raise ValueError(f"Expected {expected_rows} taxonomy rows; found {count}")
    return count


def parse_taxonkit_output(raw, parsed, input_path, expected_rows):
    """Parse the five-column output from TaxonKit lineage -c -t -R."""
    with raw.open("r", encoding="utf-8-sig") as source, input_path.open(
        "r", encoding="utf-8"
    ) as ids, parsed.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=TAXONOMY_FIELDS,
                                delimiter="\t", lineterminator="\n")
        writer.writeheader()
        count = 0
        for line, expected_id in itertools.zip_longest(source, ids):
            if line is None or expected_id is None:
                raise ValueError("TaxonKit returned a different number of lines than requested")
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) < 2 or fields[0] != expected_id.strip():
                raise ValueError(f"Malformed/misaligned TaxonKit response at row {count + 1}")
            taxid = int(fields[0])
            code = int(fields[1])
            names = {rank: "" for rank in RANKS}
            resolved = ""
            if code > 0:
                resolved = str(code)
                status = "current" if code == taxid else "merged"
                if len(fields) < 5:
                    raise ValueError(f"Missing lineage/ranks for positive TaxID: {taxid}")
                lineage_names = fields[2].split(";") if fields[2] else []
                lineage_ranks = fields[4].split(";") if fields[4] else []
                if len(lineage_names) != len(lineage_ranks):
                    raise ValueError(f"TaxonKit lineage/rank mismatch for TaxID {taxid}")
                for name, rank in zip(lineage_names, lineage_ranks):
                    if rank == "superkingdom":
                        if not names["domain"]:
                            names["domain"] = name
                    elif rank in names:
                        names[rank] = name
            elif code == 0:
                status = "deleted"
            elif code == -1:
                status = "not_found"
            else:
                raise ValueError(f"Unexpected TaxonKit status {code} for taxid {taxid}")
            writer.writerow({"taxid": taxid, "resolved_taxid": resolved,
                             "resolution_status": status,
                             **{f"rank_{rank}": names[rank] for rank in RANKS}})
            count += 1
        if count != expected_rows:
            raise ValueError(f"TaxonKit returned {count} instead of {expected_rows} rows")
    verify_parsed(parsed, input_path, expected_rows)


def run_taxonkit_batch(args, number, input_path, expected_rows):
    paths = paths_for(input_path)
    if paths["parsed"].exists() and paths["checksum"].exists():
        recorded = paths["checksum"].read_text(encoding="ascii").strip()
        if digest(paths["parsed"]) != recorded:
            raise RuntimeError(f"Cached file changed unexpectedly: {paths['parsed']}")
        verify_parsed(paths["parsed"], input_path, expected_rows)
        print(f"Batch {number}: verified cached taxonomy", flush=True)
        return paths["parsed"]

    if args.mode == "ssh":
        remote_cmd = (
            f"{shlex.quote(args.remote_taxonkit)} lineage "
            f"--data-dir {shlex.quote(args.remote_taxdb)} -c -t -R"
        )
        command = ["ssh", "-i", str(Path(args.ssh_key).expanduser()),
                   "-o", "BatchMode=yes", args.ssh_host, remote_cmd]
    else:
        binary = str(Path(args.taxonkit).expanduser()) if Path(args.taxonkit).expanduser().is_file() else args.taxonkit
        command = [binary, "lineage", "--data-dir", str(Path(args.taxdb).expanduser()),
                   "-c", "-t", "-R"]

    raw_partial = paths["raw"].with_suffix(".raw.partial")
    parsed_partial = paths["parsed"].with_suffix(".parsed.partial")
    with input_path.open("r", encoding="utf-8") as stdin_file, raw_partial.open(
        "w", encoding="utf-8", newline="\n"
    ) as stdout_file, paths["stderr"].open(
        "w", encoding="utf-8", newline="\n"
    ) as stderr_file:
        result = subprocess.run(command, stdin=stdin_file, stdout=stdout_file,
                                stderr=stderr_file, text=True, encoding="utf-8",
                                errors="replace", check=False)
    if result.returncode:
        raise RuntimeError(f"TaxonKit batch {number} failed; see {paths['stderr']}")
    parse_taxonkit_output(raw_partial, parsed_partial, input_path, expected_rows)
    parsed_partial.replace(paths["parsed"])
    paths["checksum"].write_text(digest(paths["parsed"]) + "\n", encoding="ascii")
    raw_partial.replace(paths["raw"])
    print(f"Batch {number}: resolved {expected_rows:,} TaxIDs", flush=True)
    return paths["parsed"]


def join_taxonomy(cache_dir, parsed_files):
    combined = cache_dir / "taxonomy_resolution.tsv"
    partial = cache_dir / "taxonomy_resolution.tsv.partial"
    count = 0
    with partial.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(TAXONOMY_FIELDS)
        for path in parsed_files:
            with path.open("r", encoding="utf-8", newline="") as source:
                reader = csv.reader(source, delimiter="\t")
                if next(reader) != TAXONOMY_FIELDS:
                    raise ValueError(f"Unexpected taxonomy batch header: {path}")
                for row in reader:
                    writer.writerow(row)
                    count += 1
    partial.replace(combined)
    return combined, count


def taxonomy_counts(path):
    counts = {status: 0 for status in sorted(STATUS_VALUES)}
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            counts[row["resolution_status"]] += 1
    return counts


def sql_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def validate_rollup(db, stats):
    n, distinct, total = db.execute(
        "SELECT COUNT(*), COUNT(DISTINCT taxid), COALESCE(SUM(n_records), 0) "
        "FROM taxid_locus"
    ).fetchone()
    if n != stats["taxids"] or distinct != n or total != stats["records"]:
        raise ValueError("TaxID count, uniqueness or n_records rollup failed")
    source_counts = dict(db.execute(
        "SELECT locus_id, COUNT(*) FROM record_locus WHERE status='present' "
        "GROUP BY locus_id"
    ).fetchall())
    locus_ids = stats["locus_ids"]
    sums = db.execute("SELECT " + ", ".join(
        f"COALESCE(SUM(locus_{locus_id}), 0)" for locus_id in locus_ids
    ) + " FROM taxid_locus").fetchone()
    for locus_id, count in zip(locus_ids, sums):
        if count != source_counts.get(locus_id, 0):
            raise ValueError(f"locus_{locus_id} rollup mismatch: {count} versus {source_counts.get(locus_id, 0)}")
    invalid = db.execute("SELECT 1 FROM taxid_locus WHERE " + " OR ".join(
        f"locus_{locus_id} IS NULL OR locus_{locus_id} < 0 OR locus_{locus_id} > n_records"
        for locus_id in locus_ids
    ) + " LIMIT 1").fetchone()
    if invalid:
        raise ValueError("Invalid per-TaxID locus counts")
    return n


def build_tables(database, taxonomy_file, stats, args, statuses,
                 tool_version, dump_version):
    """Build taxid_locus and build_info in a single transaction."""
    db = duckdb.connect(str(database))
    in_transaction = False
    try:
        db.execute("BEGIN TRANSACTION")
        in_transaction = True
        db.execute(f"""
            CREATE TEMP TABLE taxonomy_resolution_tmp AS
            SELECT CAST(taxid AS BIGINT) AS taxid,
                   TRY_CAST(NULLIF(resolved_taxid, '') AS BIGINT) AS resolved_taxid,
                   resolution_status,
                   {', '.join(f"NULLIF(rank_{rank}, '') AS rank_{rank}" for rank in RANKS)}
            FROM read_csv_auto({sql_quote(taxonomy_file.as_posix())},
                               delim='\\t', header=true, all_varchar=true)
        """)
        n, unique = db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT taxid) FROM taxonomy_resolution_tmp"
        ).fetchone()
        if n != stats["taxids"] or unique != n:
            raise ValueError("Taxonomy file missing or duplicating source TaxIDs")
        missing = db.execute(
            "SELECT 1 FROM (SELECT DISTINCT taxid FROM records) r "
            "LEFT JOIN taxonomy_resolution_tmp t ON r.taxid=t.taxid "
            "WHERE t.taxid IS NULL LIMIT 1"
        ).fetchone()
        if missing:
            raise ValueError("Taxonomy results do not cover every source TaxID")

        ids = stats["locus_ids"]
        pivot = ", ".join(
            f"SUM(CASE WHEN locus_id={i} THEN n_present ELSE 0 END)::BIGINT AS locus_{i}"
            for i in ids
        )
        final = ", ".join(
            f"COALESCE(p.locus_{i}, 0)::BIGINT AS locus_{i}" for i in ids
        )
        # Aggregate counts by the original TaxID; lineage fields support rank-level queries.
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
                JOIN records r ON r.accession = rl.accession
                WHERE rl.status = 'present'
                GROUP BY r.taxid, rl.locus_id
            ),
            present_counts AS (
                SELECT taxid, {pivot} FROM present_long GROUP BY taxid
            )
            SELECT c.taxid,
                   {', '.join(f't.rank_{rank}' for rank in RANKS)},
                   c.n_records, {final}
            FROM record_counts c
            LEFT JOIN taxonomy_resolution_tmp t ON t.taxid = c.taxid
            LEFT JOIN present_counts p ON p.taxid = c.taxid
        """)
        rows = validate_rollup(db, stats)
        db.execute("CREATE UNIQUE INDEX idx_taxid_locus_taxid ON taxid_locus(taxid)")
        db.execute("CREATE INDEX idx_taxid_locus_genus ON taxid_locus(rank_genus)")
        db.execute("CREATE INDEX idx_taxid_locus_species ON taxid_locus(rank_species)")

        # Absent pairs are not stored in the sparse record_locus table.
        absent = stats["records"] * len(ids) - stats["present"] - stats["unknown"]
        if absent < 0:
            raise ValueError("Impossible absent-count calculation")
        sparse_rows = db.execute("SELECT COUNT(*) FROM record_locus").fetchone()[0]
        db.execute("DROP TABLE IF EXISTS build_info")
        db.execute("""
            CREATE TABLE build_info (
                extraction_date DATE, core_nt_version TEXT, taxdump_version TEXT,
                taxonkit_version TEXT, built_at_utc TEXT,
                records_rows BIGINT, loci_rows BIGINT, record_locus_rows BIGINT,
                taxid_locus_rows BIGINT, present_count BIGINT,
                unknown_count BIGINT, absent_count BIGINT,
                distinct_taxids BIGINT, taxonomy_current BIGINT,
                taxonomy_merged BIGINT, taxonomy_deleted BIGINT,
                taxonomy_not_found BIGINT
            )
        """)
        db.execute("""
            INSERT INTO build_info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            args.extraction_date, args.core_nt_version, dump_version, tool_version,
            datetime.now(timezone.utc).isoformat(),
            stats["records"], stats["loci_rows"], sparse_rows,
            rows, stats["present"], stats["unknown"], absent,
            stats["taxids"], statuses["current"], statuses["merged"],
            statuses["deleted"], statuses["not_found"],
        ])
        if db.execute("SELECT COUNT(*) FROM build_info").fetchone()[0] != 1:
            raise ValueError("build_info is not exactly one row")
        db.execute("COMMIT")
        in_transaction = False
        return rows, absent
    except Exception:
        if in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def main():
    args = parse_arguments()
    database = validate_arguments(args)
    print("Validating input tables and locus IDs...", flush=True)
    stats = validate_database(database)
    print(f"Records: {stats['records']:,} | distinct TaxIDs: {stats['taxids']:,} | "
          f"present pairs: {stats['present']:,} | unknown pairs: {stats['unknown']:,}",
          flush=True)
    if args.check_only:
        print("Input validation complete (read-only mode)", flush=True)
        return

    work_dir = Path(args.work_dir).expanduser().resolve() if args.work_dir else (
        database.parent / f"{database.stem}_step7_cache"
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"TaxonKit execution: {args.mode}", flush=True)
    tool_version, signatures, dump_version = taxonomy_environment(args)
    print(f"TaxonKit: {tool_version} | taxdump: {dump_version}", flush=True)
    print("Reading distinct TaxIDs in batches...", flush=True)
    batches, count, taxid_digest = taxid_batches(database, work_dir, args.batch_size)
    if count != stats["taxids"]:
        raise ValueError("Distinct TaxID extraction count mismatch")
    manifest = {
        "database": str(database), "taxids": count,
        "taxid_sha256": taxid_digest, "batch_size": args.batch_size,
        "mode": args.mode, "taxonkit_version": tool_version,
        "taxdump_file_signatures": signatures,
        "taxonkit_path": args.remote_taxonkit if args.mode == "ssh" else args.taxonkit,
        "taxdb_path": args.remote_taxdb if args.mode == "ssh" else str(Path(args.taxdb).expanduser().resolve()),
    }
    check_cache(work_dir, manifest)
    parsed_files = []
    for number, input_path, rows in batches:
        print(f"Processing taxonomy batch {number}/{len(batches)}...", flush=True)
        parsed_files.append(run_taxonkit_batch(args, number, input_path, rows))
    taxonomy_file, total = join_taxonomy(work_dir, parsed_files)
    if total != count:
        raise ValueError("Combined taxonomy row count mismatch")
    statuses = taxonomy_counts(taxonomy_file)
    if sum(statuses.values()) != count:
        raise ValueError("Taxonomy status-count reconciliation failed")
    print("Taxonomy resolution: " + ", ".join(
        f"{status}={statuses[status]:,}" for status in ("current", "merged", "deleted", "not_found")
    ), flush=True)
    print("Building taxid_locus and build_info...", flush=True)
    rows, absent = build_tables(database, taxonomy_file, stats, args, statuses,
                                tool_version, dump_version)
    print(f"Build complete: {rows:,} TaxID rows | "
          f"present pairs={stats['present']:,} | unknown pairs={stats['unknown']:,} | "
          f"absent pairs={absent:,}", flush=True)
    print(f"Cache: {work_dir}", flush=True)


if __name__ == "__main__":
    main()
