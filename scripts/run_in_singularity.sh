#!/bin/bash
# Run p5_db_coverage.py inside a Singularity container with debugpy for
# VSCode remote debugging.
#
# Usage:
#   ./run_in_singularity.sh <sample_dir> <sample_id> <sif_image>
#
# Example:
#   ./run_in_singularity.sh sample_3/singularity query_001 ./taxodactyl.sif
#
# Then attach the VSCode debugger using the "Attach to Singularity" config.

set -euo pipefail

USAGE="Usage: $0 <sample_dir> <sample_id> <sif_image>"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJ_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TAXONKIT_DATA="$HOME/.taxonkit"
DEBUGPY_PORT=5678

sample_dir="${1:?$USAGE}"
SAMPLE_ID="${2:?$USAGE}"
SIF_IMAGE="${3:?$USAGE}"
WORK_DIR="$PROJ_ROOT/$sample_dir"

if [ ! -d "$WORK_DIR" ]; then
    echo "Error: Sample directory '$WORK_DIR' does not exist"
    exit 1
fi

if [ ! -f "$SIF_IMAGE" ]; then
    echo "Error: Singularity image '$SIF_IMAGE' not found"
    echo "Build it with: singularity build $SIF_IMAGE docker-daemon://<docker_image>"
    exit 1
fi

echo "Starting Singularity container with debugpy on port $DEBUGPY_PORT..."
echo "Attach VSCode debugger using 'Attach to Singularity' launch config."

singularity exec \
    --writable-tmpfs \
    -B "$TAXONKIT_DATA:$TAXONKIT_DATA" \
    -B "$PROJ_ROOT/scripts:/app/scripts" \
    -H "$WORK_DIR" \
    "$SIF_IMAGE" \
    bash --norc --noprofile -c "
        cd \$HOME
        pip install -q debugpy 2>/dev/null
        source env_vars.sh
        export TAXONKIT_DATA=$TAXONKIT_DATA
        mkdir -p $SAMPLE_ID
        cp candidates.json $SAMPLE_ID/
        python -m debugpy --listen 0.0.0.0:$DEBUGPY_PORT --wait-for-client \
            /app/scripts/p5_db_coverage.py \
            $SAMPLE_ID \
            --output-dir ./ \
            --query-fasta sequences.fasta \
            --metadata-csv metadata.csv \
            --db-coverage-toi-limit 10 \
            --db-coverage-max-candidates 3 \
            --gbif-limit-records 500 \
            --gbif-max-occurrence-records 5000 \
            --gbif-accepted-status accepted,doubtful \
            --db-cov-target-min-a 5 \
            --db-cov-target-min-b 1 \
            --db-cov-related-min-a 90 \
            --db-cov-related-min-b 10 \
            --db-cov-country-missing-a 1
    "
