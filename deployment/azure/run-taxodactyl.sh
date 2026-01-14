#!/bin/bash
#
# Run Taxodactyl workflow on Azure Batch
#
# This script runs the Taxodactyl Nextflow workflow using Azure Batch for
# compute-intensive processes (BLAST, MAFFT, FastME). Reference data is
# pre-staged to NVMe storage on Azure Batch nodes.
#
# Usage:
#   ./deployment/azure/run-taxodactyl.sh \
#       --metadata /path/to/metadata.csv \
#       --sequences /path/to/sequences.fasta \
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
METADATA="scripts/tests/test-data/metadata.csv"
SEQUENCES="scripts/tests/test-data/queries.fasta"
OUTDIR="/mnt/nvme/output/$RUN_ID"
RESUME=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --metadata)
            METADATA="$2"
            shift 2
            ;;
        --sequences)
            SEQUENCES="$2"
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
            echo "Usage: $0 --metadata <file> --sequences <file> --outdir <dir> [-resume]"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$METADATA" ]] || [[ -z "$SEQUENCES" ]] || [[ -z "$OUTDIR" ]]; then
    echo -e "${RED}ERROR: Missing required arguments${NC}"
    echo ""
    echo "Usage: $0 --metadata <file> --sequences <file> --outdir <dir> [-resume]"
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

# Azure Batch node paths (staged by start task to NVMe)
BLASTDB_PATH="/mnt/nvme/refdata/core_nt/blast/core_nt"
TAXDB_PATH="/mnt/nvme/refdata/taxdump/taxdump"

# Show configuration
echo ""
echo -e "${YELLOW}=== Taxodactyl Azure Batch Configuration ===${NC}"
echo "Metadata:      $METADATA"
echo "Sequences:     $SEQUENCES"
echo "Output dir:    $OUTDIR"
echo "BLAST DB:      $BLASTDB_PATH (on Azure Batch nodes)"
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

# Run Nextflow with Azure Batch profile
nextflow run main.nf \
    -profile azure \
    --metadata "$METADATA" \
    --sequences "$SEQUENCES" \
    --blastdb "$BLASTDB_PATH" \
    --outdir "$OUTDIR" \
    --taxdb "$TAXDB_PATH" \
    --temp_root_dir "/tmp/taxodactyl_tmp" \
    --ncbi_api_key "${NCBI_API_KEY:-}" \
    --ncbi_user_email "${NCBI_USER_EMAIL:-}" \
    --analyst_name "${ANALYST_NAME:-}" \
    --facility_name "${FACILITY_NAME:-QCIF}" \
    $RESUME

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
