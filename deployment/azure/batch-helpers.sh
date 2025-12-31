#!/bin/bash
# Azure Batch Helper Functions for Taxodactyl
#
# Usage: source deployment/azure/batch-helpers.sh
#
# This script provides convenient functions for managing Azure Batch resources.
# All destructive operations require confirmation before execution.

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DEFAULT_POOL_ID="taxodactyl"
DEFAULT_AUTOSCALE_FORMULA='initialNodes=0; maxNodes=1; demand = avg($ActiveTasks.GetSample(TimeInterval_Minute * 1)); $TargetDedicatedNodes = min(max(demand, initialNodes), maxNodes);'
DEFAULT_AUTOSCALE_INTERVAL="PT5M"

#
# Helper functions
#

_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

_confirm() {
    local prompt="$1"
    local response
    echo -ne "${YELLOW}[CONFIRM]${NC} $prompt (y/N): "
    read -r response
    [[ "$response" =~ ^[Yy]$ ]]
}

_check_env_vars() {
    local missing=()
    local required_vars=(
        "AZURE_BATCH_ACCOUNT_NAME"
        "AZURE_BATCH_ENDPOINT"
        "AZURE_STORAGE_ACCOUNT_KEY"
    )

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing+=("$var")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        _error "Missing required environment variables: ${missing[*]}"
        _info "Run 'azure_load_env' to load from .env.azure"
        return 1
    fi

    return 0
}

#
# Environment Management
#

azure_load_env() {
    local env_file="${1:-.env.azure}"

    if [[ ! -f "$env_file" ]]; then
        _error "Environment file not found: $env_file"
        return 1
    fi

    _info "Loading environment from $env_file"
    set -a
    source "$env_file"
    set +a

    _success "Environment loaded"
    _info "Batch account: ${AZURE_BATCH_ACCOUNT_NAME:-not set}"
    _info "Batch endpoint: ${AZURE_BATCH_ENDPOINT:-not set}"
    _info "Storage account (std): ${STORAGE_ACCOUNT_STD:-not set}"
    _info "Storage account (prem): ${STORAGE_ACCOUNT_PREM:-not set}"
}

#
# Pool Management
#

azure_pool_create() {
    local pool_json=""
    local enable_autoscale="true"
    local skip_confirm=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                skip_confirm=true
                shift
                ;;
            *)
                if [[ -z "$pool_json" ]]; then
                    pool_json="$1"
                else
                    enable_autoscale="$1"
                fi
                shift
                ;;
        esac
    done

    _check_env_vars || return 1

    if [[ -z "$pool_json" ]]; then
        _error "Usage: azure_pool_create <pool-config.json> [enable_autoscale=true] [--yes]"
        return 1
    fi

    if [[ ! -f "$pool_json" ]]; then
        _error "Pool configuration file not found: $pool_json"
        return 1
    fi

    # Extract pool ID from JSON
    local pool_id
    pool_id=$(grep -oP '"id"\s*:\s*"\K[^"]+' "$pool_json" | head -1)

    if [[ -z "$pool_id" ]]; then
        _error "Could not extract pool ID from $pool_json"
        return 1
    fi

    _info "Pool configuration: $pool_json"
    _info "Pool ID: $pool_id"
    _info "Autoscale: $enable_autoscale"

    if [[ "$skip_confirm" == false ]] && ! _confirm "Create pool with this configuration?"; then
        _warning "Pool creation cancelled"
        return 0
    fi

    _info "Creating pool..."

    if az batch pool create \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --json-file "$pool_json"; then

        _success "Pool '$pool_id' created successfully"

        if [[ "$enable_autoscale" == "true" ]]; then
            _info "Enabling autoscaling..."

            if az batch pool autoscale enable \
                --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
                --account-endpoint "$AZURE_BATCH_ENDPOINT" \
                --pool-id "$pool_id" \
                --auto-scale-formula "$DEFAULT_AUTOSCALE_FORMULA" \
                --auto-scale-evaluation-interval "$DEFAULT_AUTOSCALE_INTERVAL"; then

                _success "Autoscaling enabled"
            else
                _error "Failed to enable autoscaling"
                return 1
            fi
        fi
    else
        _error "Failed to create pool"
        return 1
    fi
}

azure_pool_delete() {
    local pool_id=""
    local skip_confirm=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                skip_confirm=true
                shift
                ;;
            *)
                pool_id="$1"
                shift
                ;;
        esac
    done

    # Use default if not provided
    pool_id="${pool_id:-$DEFAULT_POOL_ID}"

    _check_env_vars || return 1

    _info "Pool to delete: $pool_id"

    # Show pool info before deletion
    _info "Fetching pool information..."
    az batch pool show \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --pool-id "$pool_id" \
        --query "{id: id, state: state, vmSize: vmSize, dedicatedNodes: currentDedicatedNodes}" \
        -o table

    _warning "This will DELETE the pool and all its nodes"

    if [[ "$skip_confirm" == false ]] && ! _confirm "Are you sure you want to delete pool '$pool_id'?"; then
        _warning "Pool deletion cancelled"
        return 0
    fi

    _info "Deleting pool..."

    if az batch pool delete \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --pool-id "$pool_id" \
        --yes; then

        _success "Pool '$pool_id' deleted successfully"
    else
        _error "Failed to delete pool"
        return 1
    fi
}

azure_pool_resize() {
    local target_nodes=""
    local pool_id=""
    local skip_confirm=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                skip_confirm=true
                shift
                ;;
            *)
                if [[ -z "$target_nodes" ]]; then
                    target_nodes="$1"
                else
                    pool_id="$1"
                fi
                shift
                ;;
        esac
    done

    # Use default pool ID if not provided
    pool_id="${pool_id:-$DEFAULT_POOL_ID}"

    _check_env_vars || return 1

    if [[ -z "$target_nodes" ]]; then
        _error "Usage: azure_pool_resize <0|1> [pool_id] [--yes]"
        return 1
    fi

    if [[ ! "$target_nodes" =~ ^[0-1]$ ]]; then
        _error "Target nodes must be 0 or 1"
        return 1
    fi

    # Show current pool state
    _info "Current pool state:"
    az batch pool show \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --pool-id "$pool_id" \
        --query "{id: id, dedicatedNodes: currentDedicatedNodes, state: state}" \
        -o table

    _info "Pool: $pool_id"
    _info "Target nodes: $target_nodes"

    if [[ "$skip_confirm" == false ]] && ! _confirm "Resize pool to $target_nodes nodes?"; then
        _warning "Pool resize cancelled"
        return 0
    fi

    _info "Resizing pool..."

    if az batch pool resize \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --pool-id "$pool_id" \
        --target-dedicated-nodes "$target_nodes"; then

        _success "Pool resize initiated (target: $target_nodes nodes)"

        if [[ "$target_nodes" -eq 0 ]]; then
            _info "Pool will scale down to 0 nodes (may take a few minutes)"
        else
            _info "Pool will scale up to 1 node (may take 10-15 minutes including start task)"
        fi
    else
        _error "Failed to resize pool"
        return 1
    fi
}

azure_pool_update() {
    local pool_json=""
    local pool_id=""
    local skip_confirm=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                skip_confirm=true
                shift
                ;;
            *)
                if [[ -z "$pool_json" ]]; then
                    pool_json="$1"
                else
                    pool_id="$1"
                fi
                shift
                ;;
        esac
    done

    # Use default pool ID if not provided
    pool_id="${pool_id:-$DEFAULT_POOL_ID}"

    _check_env_vars || return 1

    if [[ -z "$pool_json" ]]; then
        _error "Usage: azure_pool_update <pool-config.json> [pool_id] [--yes]"
        return 1
    fi

    if [[ ! -f "$pool_json" ]]; then
        _error "Pool configuration file not found: $pool_json"
        return 1
    fi

    _info "Pool: $pool_id"
    _info "Configuration file: $pool_json"
    _warning "This will UPDATE the pool configuration"
    _warning "Note: Some properties (vmSize, targetDedicatedNodes) cannot be updated"

    if [[ "$skip_confirm" == false ]] && ! _confirm "Update pool '$pool_id' with this configuration?"; then
        _warning "Pool update cancelled"
        return 0
    fi

    _info "Updating pool..."

    if az batch pool set \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --pool-id "$pool_id" \
        --json-file "$pool_json"; then

        _success "Pool '$pool_id' updated successfully"
        _warning "If you updated the start task, existing nodes need to be recreated"
        _info "To recreate nodes: azure_pool_resize 0 && azure_pool_resize 1"
    else
        _error "Failed to update pool"
        return 1
    fi
}

azure_pool_list() {
    _check_env_vars || return 1

    _info "Listing all pools..."

    az batch pool list \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --query "[].{id: id, state: state, vmSize: vmSize, dedicated: currentDedicatedNodes, runningTasks: runningTasksCount}" \
        -o table
}

azure_pool_show() {
    local pool_id="${1:-$DEFAULT_POOL_ID}"

    _check_env_vars || return 1

    _info "Pool details for: $pool_id"

    az batch pool show \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --pool-id "$pool_id" \
        --query "{
            id: id,
            state: state,
            vmSize: vmSize,
            dedicatedNodes: currentDedicatedNodes,
            lowPriorityNodes: currentLowPriorityNodes,
            taskSlotsPerNode: taskSlotsPerNode,
            runningTasks: runningTasksCount,
            autoscaleEnabled: enableAutoScale
        }" \
        -o table
}

#
# Node Management
#

azure_node_list() {
    local pool_id="${1:-$DEFAULT_POOL_ID}"

    _check_env_vars || return 1

    _info "Listing nodes in pool: $pool_id"

    az batch node list \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --pool-id "$pool_id" \
        --query "[].{id: id, state: state, ip: ipAddress, startTask: startTaskInfo.state, runningTasks: runningTasksCount}" \
        -o table
}

azure_node_get_id() {
    local pool_id="${1:-$DEFAULT_POOL_ID}"
    local index="${2:-0}"

    _check_env_vars || return 1

    local node_id
    node_id=$(az batch node list \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --pool-id "$pool_id" \
        --query "[$index].id" \
        -o tsv)

    if [[ -z "$node_id" ]]; then
        _error "No nodes found in pool '$pool_id'"
        return 1
    fi

    echo "$node_id"
}

azure_node_logs() {
    local pool_id="${1:-$DEFAULT_POOL_ID}"
    local log_type="${2:-stderr}"
    local output_dir="${3:-/tmp}"

    _check_env_vars || return 1

    local node_id
    node_id=$(azure_node_get_id "$pool_id") || return 1

    _info "Pool: $pool_id"
    _info "Node: $node_id"
    _info "Log type: $log_type"

    local file_path="startup/${log_type}.txt"
    local dest_file="${output_dir}/start-task-${log_type}.txt"

    _info "Downloading start task logs..."

    if az batch node file download \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --pool-id "$pool_id" \
        --node-id "$node_id" \
        --file-path "$file_path" \
        --destination "$dest_file"; then

        _success "Logs downloaded to: $dest_file"

        # Show last 30 lines
        echo ""
        echo "=== Last 30 lines of $log_type ==="
        tail -30 "$dest_file"
        echo ""
        _info "Full logs: $dest_file"
    else
        _error "Failed to download logs"
        return 1
    fi
}

#
# Job Management
#

azure_jobs_list() {
    _check_env_vars || return 1

    _info "Listing recent jobs..."

    az batch job list \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --query "[].{id: id, state: state, poolId: poolInfo.poolId, creationTime: creationTime}" \
        -o table
}

azure_job_get_latest() {
    local pool_id="${1:-$DEFAULT_POOL_ID}"

    _check_env_vars || return 1

    local job_id
    job_id=$(az batch job list \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --query "[?poolInfo.poolId=='$pool_id'] | sort_by(@, &creationTime) | [-1].id" \
        -o tsv)

    if [[ -z "$job_id" ]]; then
        _warning "No jobs found for pool '$pool_id'"
        return 1
    fi

    echo "$job_id"
}

azure_job_logs() {
    local pool_id="${1:-$DEFAULT_POOL_ID}"

    _check_env_vars || return 1

    local job_id
    job_id=$(azure_job_get_latest "$pool_id")

    if [[ -z "$job_id" ]]; then
        _error "No jobs found for pool '$pool_id'"
        return 1
    fi

    _info "Latest job: $job_id"
    _info "Listing tasks..."

    az batch task list \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --job-id "$job_id" \
        --query "[].{id: id, state: state, exitCode: executionInfo.exitCode, startTime: executionInfo.startTime, endTime: executionInfo.endTime}" \
        -o table
}

#
# Storage Management
#

azure_storage_upload() {
    local src_file=""
    local dest_path=""
    local storage_account=""
    local container=""
    local skip_confirm=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                skip_confirm=true
                shift
                ;;
            *)
                if [[ -z "$src_file" ]]; then
                    src_file="$1"
                elif [[ -z "$dest_path" ]]; then
                    dest_path="$1"
                elif [[ -z "$storage_account" ]]; then
                    storage_account="$1"
                else
                    container="$1"
                fi
                shift
                ;;
        esac
    done

    # Use defaults if not provided
    storage_account="${storage_account:-$STORAGE_ACCOUNT_STD}"
    container="${container:-$STORAGE_CONTAINER_SCRIPTS}"

    _check_env_vars || return 1

    if [[ -z "$src_file" ]] || [[ -z "$dest_path" ]]; then
        _error "Usage: azure_storage_upload <src_file> <dest_path> [storage_account] [container] [--yes]"
        _info "Example: azure_storage_upload ./setup.sh setup.sh"
        return 1
    fi

    if [[ ! -f "$src_file" ]]; then
        _error "Source file not found: $src_file"
        return 1
    fi

    # Get file size for display
    local file_size
    file_size=$(du -h "$src_file" | cut -f1)

    _info "Source file: $src_file ($file_size)"
    _info "Destination: $dest_path"
    _info "Storage account: $storage_account"
    _info "Container: $container"

    if [[ "$skip_confirm" == false ]] && ! _confirm "Upload file to blob storage?"; then
        _warning "Upload cancelled"
        return 0
    fi

    _info "Uploading..."

    if az storage blob upload \
        --account-name "$storage_account" \
        --container-name "$container" \
        --file "$src_file" \
        --name "$dest_path" \
        --overwrite; then

        _success "File uploaded successfully"
        _info "Blob URL: https://${storage_account}.blob.core.windows.net/${container}/${dest_path}"
    else
        _error "Failed to upload file"
        return 1
    fi
}

azure_storage_download() {
    local blob_name="${1}"
    local dest_file="${2}"
    local storage_account="${3:-$STORAGE_ACCOUNT_STD}"
    local container="${4:-$STORAGE_CONTAINER_SCRIPTS}"

    _check_env_vars || return 1

    if [[ -z "$blob_name" ]] || [[ -z "$dest_file" ]]; then
        _error "Usage: azure_storage_download <blob_name> <dest_file> [storage_account] [container]"
        return 1
    fi

    _info "Downloading from: https://${storage_account}.blob.core.windows.net/${container}/${blob_name}"
    _info "Destination: $dest_file"

    if az storage blob download \
        --account-name "$storage_account" \
        --container-name "$container" \
        --name "$blob_name" \
        --file "$dest_file"; then

        _success "File downloaded to: $dest_file"
    else
        _error "Failed to download file"
        return 1
    fi
}

azure_storage_list() {
    local container="${1:-$STORAGE_CONTAINER_SCRIPTS}"
    local storage_account="${2:-$STORAGE_ACCOUNT_STD}"

    _check_env_vars || return 1

    _info "Listing blobs in: $storage_account/$container"

    az storage blob list \
        --account-name "$storage_account" \
        --container-name "$container" \
        --query "[].{name: name, size: properties.contentLength, lastModified: properties.lastModified}" \
        -o table
}

#
# SAS Token Management
#

azure_sas_generate() {
    local blob_name="${1}"
    local storage_account="${2:-$STORAGE_ACCOUNT_STD}"
    local container="${3:-$STORAGE_CONTAINER_SCRIPTS}"
    local expiry_days="${4:-365}"

    _check_env_vars || return 1

    if [[ -z "$blob_name" ]]; then
        _error "Usage: azure_sas_generate <blob_name> [storage_account] [container] [expiry_days]"
        return 1
    fi

    local expiry_date
    expiry_date=$(date -u -d "+${expiry_days} days" '+%Y-%m-%dT%H:%MZ')

    _info "Generating SAS token for: $blob_name"
    _info "Storage account: $storage_account"
    _info "Container: $container"
    _info "Expiry: $expiry_date ($expiry_days days)"

    local sas_token
    sas_token=$(az storage blob generate-sas \
        --account-name "$storage_account" \
        --container-name "$container" \
        --name "$blob_name" \
        --permissions r \
        --expiry "$expiry_date" \
        --https-only \
        --output tsv)

    if [[ -z "$sas_token" ]]; then
        _error "Failed to generate SAS token"
        return 1
    fi

    _success "SAS token generated"
    echo ""
    echo "=== Full URL with SAS token ==="
    echo "https://${storage_account}.blob.core.windows.net/${container}/${blob_name}?${sas_token}"
    echo ""
    echo "=== SAS token only ==="
    echo "$sas_token"
    echo ""
    _warning "Keep this token secure - do not commit to version control"
}

#
# Utility Functions
#

azure_help() {
    cat << 'EOF'
Azure Batch Helper Functions
=============================

Environment Management:
  azure_load_env [file]              Load environment from .env.azure (or specified file)

Pool Management:
  azure_pool_create <json> [auto] [--yes]    Create pool from JSON config (autoscale: true/false)
  azure_pool_delete [pool_id] [--yes]        Delete pool (with confirmation)
  azure_pool_resize <0|1> [pool_id] [--yes]  Resize pool to 0 or 1 persistent nodes
  azure_pool_update <json> [pool_id] [--yes] Update pool configuration from JSON
  azure_pool_list                            List all pools
  azure_pool_show [pool_id]                  Show detailed pool information

Node Management:
  azure_node_list [pool_id]         List all nodes in pool
  azure_node_get_id [pool_id] [idx]  Get node ID (by index, default: 0)
  azure_node_logs [pool] [type] [dir] Download start task logs (type: stderr/stdout)

Job Management:
  azure_jobs_list                    List all jobs
  azure_job_get_latest [pool_id]     Get latest job ID for pool
  azure_job_logs [pool_id]           Show tasks for latest job in pool

Storage Management:
  azure_storage_upload <src> <dest> [acct] [cont] [--yes]  Upload file to blob storage
  azure_storage_download <blob> <dest> [acct] [cont]       Download file from blob storage
  azure_storage_list [container] [account]                 List blobs in container

SAS Token Management:
  azure_sas_generate <blob> [acct] [cont] [days]   Generate SAS token for blob

Utility:
  azure_help                         Show this help message

Default Values:
  Pool ID: taxodactyl
  Storage Account (std): $STORAGE_ACCOUNT_STD
  Storage Account (prem): $STORAGE_ACCOUNT_PREM
  Container (scripts): $STORAGE_CONTAINER_SCRIPTS

Examples:
  # Load environment
  azure_load_env

  # Create pool with autoscaling (interactive)
  azure_pool_create deployment/azure/pool-setup.json.ignore

  # Create pool without confirmation (for scripts)
  azure_pool_create deployment/azure/pool-setup.json.ignore true --yes

  # Resize pool to 1 node
  azure_pool_resize 1

  # Resize pool to 0 nodes (skip confirmation)
  azure_pool_resize 0 --yes

  # Get start task logs
  azure_node_logs

  # Upload script to blob storage
  azure_storage_upload deployment/azure/setup.sh setup.sh

  # Upload without confirmation (for scripts)
  azure_storage_upload deployment/azure/setup.sh setup.sh --yes

  # Generate SAS token
  azure_sas_generate setup.sh

EOF
}

# Auto-load environment and show help when sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    _error "This script should be sourced, not executed directly"
    echo "Usage: source deployment/azure/batch-helpers.sh"
    exit 1
else
    _success "Azure Batch helper functions loaded"
    echo ""

    # Automatically load environment if .env.azure exists
    if [[ -f ".env.azure" ]]; then
        azure_load_env
    else
        _warning "No .env.azure file found in current directory"
        _info "Environment variables not loaded - run 'azure_load_env <file>' to load manually"
    fi

    echo ""
    echo -e "${BLUE}Available Commands:${NC}"
    echo ""
    echo "  Pool Management:"
    echo "    azure_pool_create, azure_pool_delete, azure_pool_resize"
    echo "    azure_pool_update, azure_pool_list, azure_pool_show"
    echo ""
    echo "  Node Management:"
    echo "    azure_node_list, azure_node_get_id, azure_node_logs"
    echo ""
    echo "  Job Management:"
    echo "    azure_jobs_list, azure_job_get_latest, azure_job_logs"
    echo ""
    echo "  Storage Management:"
    echo "    azure_storage_upload, azure_storage_download, azure_storage_list"
    echo ""
    echo "  SAS Token Management:"
    echo "    azure_sas_generate"
    echo ""
    echo -e "${GREEN}Run 'azure_help' for detailed usage information${NC}"
    echo ""
fi
