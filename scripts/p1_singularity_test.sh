#!/usr/bin/env bash

singularity exec \
    docker://neoformit/taxodactyl \
    python /app/scripts/p1_parse_blast.py \
    tests/test-data/output.xml
