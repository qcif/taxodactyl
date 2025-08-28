#!/usr/bin/env bash

QUERY_DIR=/output/query_001_LC438549.1
OUTPUT_DIR=/output

docker run \
    -v "$PWD/output:/output" \
    -v "$PWD/tests:/tests" \
    -v "/home/cameron/.taxonkit:/taxonkit" \
    -e "TAXONKIT_DATA=/taxonkit" \
    -e LOGGING_DEBUG=1 \
    neoformit/taxodactyl \
    python /app/scripts/p5_db_coverage.py \
    $QUERY_DIR \
    --output-dir $OUTPUT_DIR \
    --metadata-csv /tests/test-data/metadata.csv \
    --query-fasta /tests/test-data/queries.fasta \
    --gbif-max-occurrence-records 200
