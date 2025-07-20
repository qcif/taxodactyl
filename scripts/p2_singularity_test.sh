#!/usr/bin/env bash

singularity exec \
    docker://neoformit/daff-taxonomic-assignment \
    python /app/scripts/p2_extract_taxonomy.py \
    test-data/taxids.csv
