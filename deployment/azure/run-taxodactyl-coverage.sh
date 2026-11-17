#!/bin/bash
#
# Run Taxodactyl in database coverage mode on Azure Batch
#
# This script runs the Taxodactyl Nextflow workflow in database coverage mode:
# the reference database coverage of a list of target taxa is evaluated, with
# no input sequences. Each taxon is evaluated in its own Azure Batch task. No
# BLAST search is run, so only the taxdump reference data (pre-staged to NVMe
# storage on Azure Batch nodes) is needed.
#
# Usage:
#   ./deployment/azure/run-taxodactyl-coverage.sh \
#       --coverage-taxa /path/to/coverage.csv \
#       --outdir /path/to/output
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PID=$$
RUN_ID="$(date +"%Y%m%d_%H%M%S")_$PID"

# Default values
COVERAGE_TAXA="test/coverage_example.csv"
OUTDIR="output/$RUN_ID"
RESUME=""

# Azure Batch node paths (staged by start task to NVMe)
TAXDB_PATH="/mnt/nvme/refdata/taxdump/taxdump"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --coverage-taxa)
            COVERAGE_TAXA="$2"
            shift 2
            ;;
        --outdir)
            OUTDIR="$2"
            shift 2
            ;;
        -resume)
            RESUME="-resume"
            shift
            ;;
        *)
            echo -e "${RED}ERROR: Unknown argument: $1${NC}"
            echo ""
            echo "Usage: $0 --coverage-taxa <file> --outdir <dir> [-resume]"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$COVERAGE_TAXA" ]] || [[ -z "$OUTDIR" ]]; then
    echo -e "${RED}ERROR: Missing required arguments${NC}"
    echo ""
    echo "Usage: $0 --coverage-taxa <file> --outdir <dir> [-resume]"
    exit 1
fi

# Load Azure credentials
if [[ ! -f .env.azure ]]; then
    echo -e "${RED}ERROR: .env.azure not found${NC}"
    echo "Please run this script from the repository root directory"
    exit 1
fi

echo -e "${YELLOW}Loading Azure credentials from .env.azure${NC}"
set -a
source .env.azure
set +a

# Verify credentials are set
if [[ -z "${AZURE_STORAGE_ACCOUNT_KEY:-}" ]]; then
    echo -e "${RED}ERROR: AZURE_STORAGE_ACCOUNT_KEY not set in .env.azure${NC}"
    exit 1
fi

if [[ -z "${AZURE_BATCH_ACCESS_KEY:-}" ]]; then
    echo -e "${RED}ERROR: AZURE_BATCH_ACCESS_KEY not set in .env.azure${NC}"
    exit 1
fi

# Check Redis reachability if configured
if [[ "${THROTTLE_BACKEND:-}" == "redis" ]] && [[ -n "${REDIS_HOST:-}" ]]; then
    echo -e "${YELLOW}Redis backend enabled at $REDIS_HOST:${REDIS_PORT:-6379} (status unknown)${NC}"
fi

# Show configuration
echo ""
echo -e "${YELLOW}=== Taxodactyl Azure Batch Configuration ===${NC}"
echo "Coverage taxa: $COVERAGE_TAXA"
echo "Output dir:    $OUTDIR"
echo "Tax DB:        $TAXDB_PATH (on Azure Batch nodes)"
echo "Profile:       azure"
echo "Resume:        ${RESUME:-false}"
echo ""

# Confirm execution
read -p "Continue with workflow execution? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
    echo "Execution cancelled"
    exit 0
fi

echo ""
echo -e "${GREEN}=== Starting Taxodactyl Workflow ===${NC}"
echo ""

mkdir -p "$OUTDIR"

# Run Nextflow with Azure Batch profile
nextflow run main.nf \
    -profile azure \
    --coverage_taxa "$COVERAGE_TAXA" \
    --outdir "$OUTDIR" \
    --taxdb "$TAXDB_PATH" \
    --temp_root_dir ./tmp \
    --ncbi_user_email "${NCBI_USER_EMAIL:-}" \
    --analyst_name "${ANALYST_NAME:-}" \
    $RESUME

    # Will be retrieved from Az key vault:
    # --ncbi_api_key "${NCBI_API_KEY:-}" \
    # --facility_name "${FACILITY_NAME:-QCIF}" \

exit_code=$?

echo ""
if [[ $exit_code -eq 0 ]]; then
    echo -e "${GREEN}=== Workflow Completed Successfully ===${NC}"
    echo ""
    echo "Output directory: $OUTDIR"
else
    echo -e "${RED}=== Workflow Failed ===${NC}"
    echo ""
    echo "Exit code: $exit_code"
    echo "Check .nextflow.log for details"
fi

exit $exit_code
