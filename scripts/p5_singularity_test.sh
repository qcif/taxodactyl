#!/usr/bin/env bash

# This should be parallelized with one process per query directory

QUERY_DIR=test-data/query_1/
OUTPUT_DIR=test-data/

singularity exec \
    docker://neoformit/daff-taxonomic-assignment \
    python /app/scripts/p5_db_coverage.py \
    $QUERY_DIR \
    --output-dir $OUTPUT_DIR
