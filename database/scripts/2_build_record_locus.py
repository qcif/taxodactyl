import argparse
import json
import re
from pathlib import Path

import duckdb
import pandas as pd


def parse_arguments():
    """Read command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build loci and sparse record_locus tables."
    )

    parser.add_argument(
        "--db",
        required=True,
        help="Path to the DuckDB database created in Step 5.",
    )

    parser.add_argument(
        "--loci-config",
        default="scripts/config/loci.json",
        help="Path to loci.json.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional record limit for development testing.",
    )

    return parser.parse_args()


def load_loci_registry(loci_config_path):
    """Load the official 31-locus configuration."""
    config_path = Path(loci_config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Loci configuration file not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as config_file:
        loci_config = json.load(config_file)

    if len(loci_config) != 31:
        raise ValueError(
            f"Expected 31 loci, found {len(loci_config)}"
        )

    return loci_config


def build_locus_id_mapping(loci_config):
    """Assign stable IDs using the current registry order."""
    return {
        locus_name: locus_id
        for locus_id, locus_name in enumerate(
            loci_config.keys(),
            start=1,
        )
    }


def build_loci_rows(loci_config, locus_id_mapping):
    """Prepare one database row per configured synonym."""
    rows = []

    for locus_name, locus_data in loci_config.items():
        locus_id = locus_id_mapping[locus_name]

        for synonym in locus_data["ambiguous_synonyms"]:
            rows.append(
                (
                    locus_id,
                    locus_name,
                    synonym,
                    "ambiguous",
                )
            )

        for synonym in locus_data["non_ambiguous_synonyms"]:
            rows.append(
                (
                    locus_id,
                    locus_name,
                    synonym,
                    "non_ambiguous",
                )
            )

    return rows


def validate_database(database_path):
    """Verify that the Step 5 records table exists."""
    db_path = Path(database_path)

    if not db_path.exists():
        raise FileNotFoundError(
            f"DuckDB database not found: {db_path}"
        )

    connection = duckdb.connect(
        str(db_path),
        read_only=True,
    )

    try:
        records_exists = connection.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'records'
            """
        ).fetchone()[0]

        if records_exists == 0:
            raise ValueError(
                "The database does not contain the records table."
            )

        record_count = connection.execute(
            "SELECT COUNT(*) FROM records"
        ).fetchone()[0]

    finally:
        connection.close()

    return record_count


def create_loci_table(
    database_path,
    loci_rows,
    locus_id_mapping,
):
    """Create or rebuild the loci registry table."""
    connection = duckdb.connect(
        str(Path(database_path))
    )

    try:
        table_exists = connection.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'loci'
            """
        ).fetchone()[0]

        if table_exists:
            existing_mapping = dict(
                connection.execute(
                    """
                    SELECT DISTINCT name, locus_id
                    FROM loci
                    """
                ).fetchall()
            )

            if existing_mapping != locus_id_mapping:
                raise ValueError(
                    "Existing locus_id mapping does not match "
                    "the current mapping."
                )

        else:
            connection.execute(
                """
                CREATE TABLE loci (
                    locus_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    synonym TEXT NOT NULL,
                    ambiguity_class TEXT NOT NULL
                )
                """
            )

        connection.execute("DELETE FROM loci")

        connection.executemany(
            """
            INSERT INTO loci (
                locus_id,
                name,
                synonym,
                ambiguity_class
            )
            VALUES (?, ?, ?, ?)
            """,
            loci_rows,
        )

        row_count = connection.execute(
            "SELECT COUNT(*) FROM loci"
        ).fetchone()[0]

        distinct_loci = connection.execute(
            """
            SELECT COUNT(DISTINCT locus_id)
            FROM loci
            """
        ).fetchone()[0]

    finally:
        connection.close()

    return row_count, distinct_loci


def compile_complete_genome_pattern():
    """Compile conservative complete-genome title patterns."""
    return re.compile(
        r"\bcomplete\s+genome\b"
        r"|\bcomplete\s+mitochondrial\s+genome\b"
        r"|\bcomplete\s+chromosome\b"
        r"|\bchloroplast\s+genome\b",
        re.IGNORECASE,
    )


def normalize_synonym(text):
    """
    Normalize case and separators.

    Spaces and hyphens become a single space so configured synonyms
    match titles containing either separator style.
    """
    return re.sub(
        r"[\s-]+",
        " ",
        text.strip().lower(),
    )


def build_one_pass_matcher(
    loci_config,
    locus_id_mapping,
):
    """
    Build one combined synonym regex and map each matched term
    back to all locus IDs that it represents.
    """
    locus_synonyms = {}
    all_synonyms = set()

    for locus_name, locus_data in loci_config.items():
        locus_id = locus_id_mapping[locus_name]

        synonyms = (
            locus_data["ambiguous_synonyms"]
            + locus_data["non_ambiguous_synonyms"]
        )

        normalized_synonyms = [
            normalize_synonym(synonym)
            for synonym in synonyms
        ]

        locus_synonyms[locus_id] = normalized_synonyms
        all_synonyms.update(normalized_synonyms)

    # Longest first protects overlapping terms such as ITS / ITS1.
    sorted_synonyms = sorted(
        all_synonyms,
        key=len,
        reverse=True,
    )

    combined_pattern = re.compile(
        r"(?<!\w)(?:"
        + "|".join(
            re.escape(synonym)
            for synonym in sorted_synonyms
        )
        + r")(?!\w)"
    )

    # A matched long synonym can satisfy more than one locus.
    # Example: "internal transcribed spacer 1" can also imply ITS.
    match_to_loci = {}

    for matched_term in sorted_synonyms:
        matched_loci = []

        for locus_id, synonyms in locus_synonyms.items():
            for synonym in synonyms:
                synonym_pattern = re.compile(
                    r"(?<!\w)"
                    + re.escape(synonym)
                    + r"(?!\w)"
                )

                if synonym_pattern.search(matched_term):
                    matched_loci.append(locus_id)
                    break

        match_to_loci[matched_term] = matched_loci

    return combined_pattern, match_to_loci


def create_record_locus_table(database_path):
    """
    Create the sparse record_locus table.

    Missing accession/locus pairs mean absent.
    """
    connection = duckdb.connect(
        str(Path(database_path))
    )

    try:
        connection.execute(
            "DROP TABLE IF EXISTS record_locus"
        )

        connection.execute(
            """
            CREATE TABLE record_locus (
                accession TEXT NOT NULL,
                locus_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                evidence_source TEXT NOT NULL
            )
            """
        )

    finally:
        connection.close()


def create_record_locus_indexes(database_path):
    """Create uniqueness and lookup indexes after bulk loading."""
    connection = duckdb.connect(
        str(Path(database_path))
    )

    try:
        connection.execute(
            """
            CREATE UNIQUE INDEX idx_record_locus_unique
            ON record_locus(accession, locus_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX idx_record_locus_accession
            ON record_locus(accession)
            """
        )

        connection.execute(
            """
            CREATE INDEX idx_record_locus_locus_status
            ON record_locus(locus_id, status)
            """
        )

    finally:
        connection.close()

def populate_record_locus(
    database_path,
    complete_genome_pattern,
    combined_locus_pattern,
    match_to_loci,
    locus_ids,
    record_batch_size=50000,
    limit=None,
):
    """
    Populate record_locus using one combined synonym scan.

    Reads and writes are performed batch-by-batch using one DuckDB
    connection. This avoids keeping a long-running read cursor open
    while another connection modifies the database.

    Missing record/locus combinations represent absent.
    """
    db_path = str(Path(database_path))

    connection = duckdb.connect(db_path)

    processed_records = 0
    inserted_rows = 0
    present_rows = 0
    unknown_rows = 0

    locus_ids_df = pd.DataFrame(
        {"locus_id": locus_ids}
    )

    try:
        while True:
            if limit is not None:
                remaining = limit - processed_records

                if remaining <= 0:
                    break

                rows_to_read = min(
                    record_batch_size,
                    remaining,
                )
            else:
                rows_to_read = record_batch_size

            # Read only one completed batch at a time.
            # No long-running SELECT cursor remains open.
            rows = connection.execute(
                f"""
                SELECT accession, title
                FROM records
                LIMIT {rows_to_read}
                OFFSET {processed_records}
                """
            ).fetchall()

            if not rows:
                break

            batch_df = pd.DataFrame(
                rows,
                columns=[
                    "accession",
                    "title",
                ],
            )

            titles = (
                batch_df["title"]
                .fillna("")
                .astype(str)
            )

            # Complete-genome records are unknown for all 31 loci.
            unknown_mask = titles.str.contains(
                complete_genome_pattern,
                regex=True,
                na=False,
            )

            sparse_frames = []

            if unknown_mask.any():
                unknown_accessions = (
                    batch_df.loc[
                        unknown_mask,
                        ["accession"],
                    ]
                    .reset_index(drop=True)
                )

                unknown_df = unknown_accessions.merge(
                    locus_ids_df,
                    how="cross",
                )

                unknown_df["status"] = "unknown"
                unknown_df["evidence_source"] = "title"

                unknown_rows += len(unknown_df)

                sparse_frames.append(unknown_df)

            # Complete-genome records are not assessed as present.
            assessable_df = batch_df.loc[
                ~unknown_mask
            ].copy()

            if not assessable_df.empty:
                normalized_titles = (
                    assessable_df["title"]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.replace(
                        r"[\s-]+",
                        " ",
                        regex=True,
                    )
                )

                # One combined regex scan.
                matches = normalized_titles.str.findall(
                    combined_locus_pattern
                )

                exploded_matches = (
                    matches
                    .explode()
                    .dropna()
                )

                if not exploded_matches.empty:
                    locus_matches = (
                        exploded_matches
                        .map(match_to_loci)
                        .explode()
                        .dropna()
                    )

                    present_pairs = pd.DataFrame(
                        {
                            "row_id": locus_matches.index,
                            "locus_id": (
                                locus_matches.astype(int).values
                            ),
                        }
                    )

                    present_pairs = (
                        present_pairs.drop_duplicates(
                            ["row_id", "locus_id"]
                        )
                    )

                    present_df = present_pairs.merge(
                        assessable_df[["accession"]],
                        left_on="row_id",
                        right_index=True,
                        how="left",
                    )

                    present_df = present_df[
                        ["accession", "locus_id"]
                    ]

                    present_df["status"] = "present"
                    present_df["evidence_source"] = "title"

                    present_rows += len(present_df)

                    sparse_frames.append(present_df)

            if sparse_frames:
                sparse_batch = pd.concat(
                    sparse_frames,
                    ignore_index=True,
                )

                connection.register(
                    "record_locus_batch",
                    sparse_batch,
                )

                try:
                    connection.execute(
                        """
                        INSERT INTO record_locus
                        SELECT
                            accession,
                            locus_id,
                            status,
                            evidence_source
                        FROM record_locus_batch
                        """
                    )

                finally:
                    connection.unregister(
                        "record_locus_batch"
                    )

                inserted_rows += len(sparse_batch)

            processed_records += len(batch_df)

            if processed_records % 100000 == 0:
                print(
                    f"Processed "
                    f"{processed_records:,} "
                    f"records..."
                )

    finally:
        connection.close()

    return (
        processed_records,
        inserted_rows,
        present_rows,
        unknown_rows,
    )

if __name__ == "__main__":
    args = parse_arguments()

    loci_config = load_loci_registry(
        args.loci_config
    )

    locus_id_mapping = build_locus_id_mapping(
        loci_config
    )

    loci_rows = build_loci_rows(
        loci_config,
        locus_id_mapping,
    )

    complete_genome_pattern = (
        compile_complete_genome_pattern()
    )

    (
        combined_locus_pattern,
        match_to_loci,
    ) = build_one_pass_matcher(
        loci_config,
        locus_id_mapping,
    )

    locus_ids = list(
        locus_id_mapping.values()
    )

    record_count = validate_database(
        args.db
    )

    (
        loci_row_count,
        distinct_loci,
    ) = create_loci_table(
        args.db,
        loci_rows,
        locus_id_mapping,
    )

    create_record_locus_table(
        args.db
    )

    (
        processed_records,
        inserted_rows,
        present_rows,
        unknown_rows,
    ) = populate_record_locus(
        args.db,
        complete_genome_pattern,
        combined_locus_pattern,
        match_to_loci,
        locus_ids,
        limit=args.limit,
    )

    create_record_locus_indexes(
        args.db
    )

    print(f"Loci loaded: {len(loci_config)}")
    print(f"Records available: {record_count:,}")
    print(f"Locus synonym rows prepared: {len(loci_rows)}")
    print(f"Loci table rows: {loci_row_count}")
    print(f"Distinct locus IDs: {distinct_loci}")
    print(f"Records classified: {processed_records:,}")
    print(f"Sparse rows inserted: {inserted_rows:,}")
    print(f"Present rows: {present_rows:,}")
    print(f"Unknown rows: {unknown_rows:,}")