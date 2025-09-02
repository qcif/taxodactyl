#!/usr/bin/env bash

singularity exec \
    docker://neoformit/taxodactyl \
    python /app/scripts/p2_extract_taxonomy.py \
    test-data/taxids.csv
