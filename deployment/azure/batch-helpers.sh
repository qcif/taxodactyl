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
DEFAULT_AUTOSCALE_INTERVAL="PT5M"

# Redis VM
REDIS_VM_NAME="daff-redis-vm"
REDIS_VM_HOST="daff-redis.australiaeast.cloudapp.azure.com"
REDIS_VM_NSG="daff-redis-nsg"
REDIS_VM_TYPE="Standard_B2ats_v2"

# Autoscale formula: Fast scale-up (5min window), slow scale-down (30min window)
# Scales to 1 node if ANY tasks in last 5 min OR any tasks in last 30 min
# This ensures quick response to new tasks while keeping nodes warm
DEFAULT_AUTOSCALE_FORMULA='
interval = TimeInterval_Minute * 60;

// Compute the target nodes based on pending tasks.
$tasks = max( $PendingTasks.GetSample(1), avg($PendingTasks.GetSample(interval)));
targetPoolSize = $tasks > 0 ? 2 : 0;
$TargetDedicatedNodes = targetPoolSize;
$NodeDeallocationOption = taskcompletion;'

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
        _info "Run 'az_load_env' to load from .env.azure"
        return 1
    fi

    return 0
}

#
# Environment Management
#

az_load_env() {
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

az_pool_assign_identity() {
    local pool_id="${1:-$DEFAULT_POOL_ID}"

    local missing=()
    for var in RESOURCE_GROUP MANAGED_IDENTITY_NAME AZURE_BATCH_ACCOUNT_NAME; do
        [[ -z "${!var}" ]] && missing+=("$var")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        _error "Missing required environment variables: ${missing[*]}"
        _info "Run 'az_load_env' to load from .env.azure"
        return 1
    fi

    _info "Fetching subscription ID..."
    local sub_id
    sub_id=$(az account show --query id -o tsv)

    _info "Fetching managed identity resource ID..."
    local identity_id
    identity_id=$(az identity show \
        --name "$MANAGED_IDENTITY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query id -o tsv)

    if [[ -z "$identity_id" ]]; then
        _error "Managed identity '$MANAGED_IDENTITY_NAME' not found in '$RESOURCE_GROUP'"
        return 1
    fi

    local pool_arm_id="/subscriptions/${sub_id}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Batch/batchAccounts/${AZURE_BATCH_ACCOUNT_NAME}/pools/${pool_id}"

    _info "Pool:     $pool_id"
    _info "Identity: $identity_id"

    if az rest \
        --method patch \
        --url "${pool_arm_id}?api-version=2024-02-01" \
        --body "{\"identity\": {\"type\": \"UserAssigned\", \"userAssignedIdentities\": {\"${identity_id}\": {}}}}"; then

        _success "Managed identity assigned to pool '$pool_id'"
    else
        _error "Failed to assign managed identity"
        return 1
    fi
}

az_pool_create() {
    local pool_json=""
    local enable_autoscale=false
    local skip_confirm=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                pool_json="$2"
                shift 2
                ;;
            --autoscale)
                enable_autoscale=true
                shift
                ;;
            --yes|-y)
                skip_confirm=true
                shift
                ;;
            *)
                _error "Unknown argument: $1"
                _error "Usage: az_pool_create --json <pool-config.json> [--autoscale] [--yes]"
                return 1
                ;;
        esac
    done

    _check_env_vars || return 1

    if [[ -z "$pool_json" ]]; then
        _error "Usage: az_pool_create --json <pool-config.json> [--autoscale] [--yes]"
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

        if [[ -n "$MANAGED_IDENTITY_NAME" ]]; then
            _info "Assigning managed identity '$MANAGED_IDENTITY_NAME' to pool..."
            az_pool_assign_identity "$pool_id" || return 1
        else
            _warning "MANAGED_IDENTITY_NAME not set — skipping managed identity assignment"
            _warning "Batch nodes will not have Key Vault access. Set MANAGED_IDENTITY_NAME in .env.azure and run az_pool_assign_identity."
        fi

        if [[ "$enable_autoscale" == true ]]; then
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

az_pool_delete() {
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

az_pool_resize() {
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
        _error "Usage: az_pool_resize <0|1> [pool_id] [--yes]"
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

az_pool_update() {
    local pool_json=""
    local pool_id=""
    local enable_autoscale=false
    local skip_confirm=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                pool_json="$2"
                shift 2
                ;;
            --pool-id)
                pool_id="$2"
                shift 2
                ;;
            --autoscale)
                enable_autoscale=true
                shift
                ;;
            --yes|-y)
                skip_confirm=true
                shift
                ;;
            *)
                # Positional argument is pool ID
                if [[ -z "$pool_id" ]]; then
                    pool_id="$1"
                else
                    _error "Unknown argument: $1"
                    _error "Usage: az_pool_update --json <pool-config.json> [--pool-id <id>] [--autoscale] [--yes]"
                    _error "   or: az_pool_update --autoscale [pool_id] [--yes]"
                    return 1
                fi
                shift
                ;;
        esac
    done

    # Use default pool ID if not provided
    pool_id="${pool_id:-$DEFAULT_POOL_ID}"

    _check_env_vars || return 1

    # If no JSON and no autoscale flag, show error
    if [[ -z "$pool_json" ]] && [[ "$enable_autoscale" == false ]]; then
        _error "Usage: az_pool_update --json <pool-config.json> [--pool-id <id>] [--autoscale] [--yes]"
        _error "   or: az_pool_update --autoscale [pool_id] [--yes]"
        return 1
    fi

    _info "Pool: $pool_id"
    if [[ -n "$pool_json" ]]; then
        if [[ ! -f "$pool_json" ]]; then
            _error "Pool configuration file not found: $pool_json"
            return 1
        fi
        _info "Configuration file: $pool_json"
    fi
    _info "Autoscale: $enable_autoscale"

    # Build confirmation message
    local confirm_msg="Update pool '$pool_id'"
    if [[ -n "$pool_json" ]]; then
        confirm_msg="$confirm_msg with configuration from $pool_json"
    fi
    if [[ "$enable_autoscale" == true ]]; then
        confirm_msg="$confirm_msg and enable autoscaling"
    fi
    confirm_msg="$confirm_msg?"

    if [[ "$skip_confirm" == false ]] && ! _confirm "$confirm_msg"; then
        _warning "Pool update cancelled"
        return 0
    fi

    # Update pool configuration if JSON provided
    if [[ -n "$pool_json" ]]; then
        _warning "This will UPDATE the pool configuration"
        _warning "Note: Some properties (vmSize, targetDedicatedNodes) cannot be updated"
        _info "Updating pool configuration..."

        if ! az batch pool set \
            --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
            --account-endpoint "$AZURE_BATCH_ENDPOINT" \
            --pool-id "$pool_id" \
            --json-file "$pool_json"; then

            _error "Failed to update pool configuration"
            return 1
        fi

        _success "Pool '$pool_id' updated successfully"
    fi

    # Enable autoscaling if requested
    if [[ "$enable_autoscale" == true ]]; then
        _info "Enabling autoscaling..."

        if az batch pool autoscale enable \
            --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
            --account-endpoint "$AZURE_BATCH_ENDPOINT" \
            --pool-id "$pool_id" \
            --auto-scale-formula "$DEFAULT_AUTOSCALE_FORMULA" \
            --auto-scale-evaluation-interval "$DEFAULT_AUTOSCALE_INTERVAL"; then

            _success "Autoscaling enabled for pool '$pool_id'"
        else
            _error "Failed to enable autoscaling"
            return 1
        fi
    fi

    if [[ -n "$pool_json" ]]; then
        _warning "If you updated the start task, existing nodes need to be recreated"
        _info "To recreate nodes: az_pool_resize 0 --yes && az_pool_resize 1"
    fi
}

az_pool_list() {
    _check_env_vars || return 1

    _info "Listing all pools..."

    az batch pool list \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --query "[].{Id: id, State: state, VmSize: vmSize, Dedicated: currentDedicatedNodes, RunningTasks: runningTasksCount}" \
        -o table
}

az_pool_show() {
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

az_node_list() {
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

az_node_get_id() {
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

az_node_logs() {
    local pool_id="${1:-$DEFAULT_POOL_ID}"
    local log_type="${2:-stderr}"
    local output_dir="${3:-/tmp}"

    _check_env_vars || return 1

    local node_id
    node_id=$(az_node_get_id "$pool_id") || return 1

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

az_jobs_list() {
    _check_env_vars || return 1

    _info "Listing recent jobs..."

    az batch job list \
        --account-name "$AZURE_BATCH_ACCOUNT_NAME" \
        --account-endpoint "$AZURE_BATCH_ENDPOINT" \
        --query "[].{id: id, state: state, poolId: poolInfo.poolId, creationTime: creationTime}" \
        -o table
}

az_job_get_latest() {
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

az_job_logs() {
    local pool_id="${1:-$DEFAULT_POOL_ID}"

    _check_env_vars || return 1

    local job_id
    job_id=$(az_job_get_latest "$pool_id")

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

az_storage_upload() {
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
        _error "Usage: az_storage_upload <src_file> <dest_path> [storage_account] [container] [--yes]"
        _info "Example: az_storage_upload ./setup.sh setup.sh"
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

az_storage_download() {
    local blob_name="${1}"
    local dest_file="${2}"
    local storage_account="${3:-$STORAGE_ACCOUNT_STD}"
    local container="${4:-$STORAGE_CONTAINER_SCRIPTS}"

    _check_env_vars || return 1

    if [[ -z "$blob_name" ]] || [[ -z "$dest_file" ]]; then
        _error "Usage: az_storage_download <blob_name> <dest_file> [storage_account] [container]"
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

az_storage_list() {
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

az_sas_generate() {
    local blob_name="${1}"
    local storage_account="${2:-$STORAGE_ACCOUNT_STD}"
    local container="${3:-$STORAGE_CONTAINER_SCRIPTS}"
    local expiry_days="${4:-365}"

    _check_env_vars || return 1

    if [[ -z "$blob_name" ]]; then
        _error "Usage: az_sas_generate <blob_name> [storage_account] [container] [expiry_days]"
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
# Nextflow Debugging Functions
#

az_fetch_nf_logs() {
    local nf_log="${1:-.nextflow.log}"
    local output_dir="${2:-./.nextflow_logs}"

    _check_env_vars || return 1

    if [[ ! -f "$nf_log" ]]; then
        _error "Nextflow log file not found: $nf_log"
        return 1
    fi

    _info "Extracting work directories from: $nf_log"

    # Extract all work directories from the log
    local work_dirs=($(grep -o "work/[a-f0-9][a-f0-9]/[a-f0-9]*" "$nf_log" | sort -u))

    if [[ ${#work_dirs[@]} -eq 0 ]]; then
        _error "No work directories found in $nf_log"
        return 1
    fi

    _info "Found ${#work_dirs[@]} work directories"
    _info "Output directory: $output_dir"

    # Create output directory
    mkdir -p "$output_dir"

    # Download .command.out and .command.err for each work directory
    local count=0
    for workdir in "${work_dirs[@]}"; do
        local short_hash=$(echo "$workdir" | grep -o '[a-f0-9]*$' | cut -c1-8)

        _info "[$((++count))/${#work_dirs[@]}] Downloading logs for $short_hash..."

        # Download .command.out
        if az storage blob download \
            --account-name daffstandard \
            --account-key "$AZURE_STORAGE_ACCOUNT_KEY" \
            --container-name workdata \
            --name "$workdir/.command.out" \
            --file "$output_dir/${short_hash}.command.out" \
            --only-show-errors 2>&1 | grep -v "^$" > /dev/null; then
            :
        fi

        # Download .command.err
        if az storage blob download \
            --account-name daffstandard \
            --account-key "$AZURE_STORAGE_ACCOUNT_KEY" \
            --container-name workdata \
            --name "$workdir/.command.err" \
            --file "$output_dir/${short_hash}.command.err" \
            --only-show-errors 2>&1 | grep -v "^$" > /dev/null; then
            :
        fi

        # Download .command.sh for reference
        if az storage blob download \
            --account-name daffstandard \
            --account-key "$AZURE_STORAGE_ACCOUNT_KEY" \
            --container-name workdata \
            --name "$workdir/.command.sh" \
            --file "$output_dir/${short_hash}.command.sh" \
            --only-show-errors 2>&1 | grep -v "^$" > /dev/null; then
            :
        fi

        # Download .exitcode
        if az storage blob download \
            --account-name daffstandard \
            --account-key "$AZURE_STORAGE_ACCOUNT_KEY" \
            --container-name workdata \
            --name "$workdir/.exitcode" \
            --file "$output_dir/${short_hash}.exitcode" \
            --only-show-errors 2>&1 | grep -v "^$" > /dev/null; then
            :
        fi
    done

    _success "Downloaded logs for ${#work_dirs[@]} tasks to: $output_dir"
    echo ""
    _info "Files downloaded:"
    ls -lh "$output_dir" | tail -n +2 | awk '{printf "  %s %s\n", $9, $5}'
    echo ""

    # Show summary of non-empty error files
    _info "Tasks with errors (non-empty .command.err):"
    local has_errors=false
    for err_file in "$output_dir"/*.command.err; do
        if [[ -s "$err_file" ]]; then
            local hash=$(basename "$err_file" .command.err)
            local size=$(du -h "$err_file" | cut -f1)
            echo "  $hash ($size)"
            has_errors=true
        fi
    done

    if [[ "$has_errors" == false ]]; then
        echo "  (none)"
    fi
    echo ""

    # Show exit codes
    _info "Task exit codes:"
    for exitcode_file in "$output_dir"/*.exitcode; do
        if [[ -f "$exitcode_file" ]]; then
            local hash=$(basename "$exitcode_file" .exitcode)
            local exitcode=$(cat "$exitcode_file" 2>/dev/null || echo "?")
            if [[ "$exitcode" != "0" ]]; then
                echo "  $hash: $exitcode [FAILED]"
            else
                echo "  $hash: $exitcode"
            fi
        fi
    done
}

#
# Redis VM Management
#

az_redis_vm_status() {
    _check_env_vars || return 1

    _info "Redis VM: $REDIS_VM_NAME"
    echo ""

    local power_state
    power_state=$(az vm get-instance-view \
        --resource-group "$RESOURCE_GROUP" \
        --name "$REDIS_VM_NAME" \
        --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus" \
        -o tsv 2>/dev/null)

    if [[ -z "$power_state" ]]; then
        _error "VM '$REDIS_VM_NAME' not found in resource group '$RESOURCE_GROUP'"
        return 1
    fi

    echo -e "  Power state:  $power_state"
    echo -e "  Hostname:     $REDIS_VM_HOST"
    echo -e "  Port:         ${REDIS_PORT:-6379}"
    echo ""

    if [[ "$power_state" == "VM running" ]]; then
        if nc -z -w3 "$REDIS_VM_HOST" "${REDIS_PORT:-6379}" 2>/dev/null; then
            _success "Redis is reachable at $REDIS_VM_HOST:${REDIS_PORT:-6379}"
        else
            _warning "VM is running but Redis port is not reachable (this may be normal if you are accessing the VM from outside the Azure network)"
            _info "Check Redis service: az_redis_vm_ssh then 'sudo systemctl status redis-server'"
        fi
    fi
}

az_redis_vm_start() {
    local skip_confirm=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y) skip_confirm=true; shift ;;
            *) _error "Unknown argument: $1"; return 1 ;;
        esac
    done

    _check_env_vars || return 1

    local power_state
    power_state=$(az vm get-instance-view \
        --resource-group "$RESOURCE_GROUP" \
        --name "$REDIS_VM_NAME" \
        --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus" \
        -o tsv 2>/dev/null)

    if [[ "$power_state" == "VM running" ]]; then
        _info "Redis VM is already running"
        return 0
    fi

    _info "Starting Redis VM '$REDIS_VM_NAME' (current state: ${power_state:-unknown})..."

    if [[ "$skip_confirm" == false ]] && ! _confirm "Start Redis VM?"; then
        _warning "Start cancelled"
        return 0
    fi

    if az vm start \
        --resource-group "$RESOURCE_GROUP" \
        --name "$REDIS_VM_NAME"; then
        _success "Redis VM started"
        _info "Redis available at $REDIS_VM_HOST:${REDIS_PORT:-6379}"
    else
        _error "Failed to start Redis VM"
        return 1
    fi
}

az_redis_vm_stop() {
    local skip_confirm=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y) skip_confirm=true; shift ;;
            *) _error "Unknown argument: $1"; return 1 ;;
        esac
    done

    _check_env_vars || return 1

    _warning "Stopping Redis VM will make rate-limiting unavailable until restarted"
    _info "VM: $REDIS_VM_NAME"

    if [[ "$skip_confirm" == false ]] && ! _confirm "Deallocate Redis VM?"; then
        _warning "Stop cancelled"
        return 0
    fi

    _info "Deallocating Redis VM..."

    if az vm deallocate \
        --resource-group "$RESOURCE_GROUP" \
        --name "$REDIS_VM_NAME"; then
        _success "Redis VM deallocated (compute cost stopped)"
    else
        _error "Failed to deallocate Redis VM"
        return 1
    fi
}

az_redis_vm_ssh() {
    _check_env_vars || return 1

    _info "Connecting to Redis VM at $REDIS_VM_HOST..."
    ssh "azureuser@$REDIS_VM_HOST"
}

#
# Identity Management
#

_check_identity_env_vars() {
    local missing=()
    local required_vars=(
        "RESOURCE_GROUP"
        "MANAGED_IDENTITY_NAME"
        "REGION"
    )

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing+=("$var")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        _error "Missing required environment variables: ${missing[*]}"
        _info "Run 'az_load_env' to load from .env.azure"
        return 1
    fi

    return 0
}

az_identity_create() {
    local skip_confirm=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                skip_confirm=true
                shift
                ;;
            *)
                _error "Unknown argument: $1"
                _error "Usage: az_identity_create [--yes]"
                return 1
                ;;
        esac
    done

    _check_identity_env_vars || return 1

    _info "Identity name:  $MANAGED_IDENTITY_NAME"
    _info "Resource group: $RESOURCE_GROUP"
    _info "Region:         $REGION"

    if [[ "$skip_confirm" == false ]] && ! _confirm "Create managed identity '$MANAGED_IDENTITY_NAME'?"; then
        _warning "Managed identity creation cancelled"
        return 0
    fi

    _info "Creating managed identity..."

    local result
    result=$(az identity create \
        --name "$MANAGED_IDENTITY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$REGION")

    if [[ $? -ne 0 ]]; then
        _error "Failed to create managed identity"
        return 1
    fi

    local principal_id resource_id
    principal_id=$(echo "$result" | grep -oP '"principalId":\s*"\K[^"]+')
    resource_id=$(echo "$result" | grep -oP '"id":\s*"\K[^"]+' | head -1)

    _success "Managed identity '$MANAGED_IDENTITY_NAME' created"
    _info "Principal ID:  $principal_id"
    _info "Resource ID:   $resource_id"
    _info ""
    _info "Next steps:"
    _info "  1. Add the resource ID to the pool JSON 'identity' block (see 02-pool-management.md)"
    _info "  2. Grant Key Vault access: az_kv_grant_access --principal $principal_id --role user"
}

az_identity_show() {
    _check_identity_env_vars || return 1

    _info "Managed identity: $MANAGED_IDENTITY_NAME"

    az identity show \
        --name "$MANAGED_IDENTITY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "{name: name, principalId: principalId, clientId: clientId, resourceId: id}" \
        -o table
}

#
# Key Vault Management
#

_check_kv_env_vars() {
    local missing=()
    local required_vars=(
        "RESOURCE_GROUP"
        "KEY_VAULT_NAME"
    )

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing+=("$var")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        _error "Missing required environment variables: ${missing[*]}"
        _info "Run 'az_load_env' to load from .env.azure"
        return 1
    fi

    return 0
}

az_kv_create() {
    local skip_confirm=false
    local region="${REGION:-australiaeast}"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                skip_confirm=true
                shift
                ;;
            --region)
                region="$2"
                shift 2
                ;;
            *)
                _error "Unknown argument: $1"
                _error "Usage: az_kv_create [--region <region>] [--yes]"
                return 1
                ;;
        esac
    done

    _check_kv_env_vars || return 1

    local kv_url="https://${KEY_VAULT_NAME}.vault.azure.net/"

    _info "Key Vault name:   $KEY_VAULT_NAME"
    _info "Resource group:   $RESOURCE_GROUP"
    _info "Region:           $region"
    _info "Vault URL:        $kv_url"
    _info "Access model:     Azure RBAC"

    if [[ "$skip_confirm" == false ]] && ! _confirm "Create Key Vault '$KEY_VAULT_NAME'?"; then
        _warning "Key Vault creation cancelled"
        return 0
    fi

    _info "Creating Key Vault..."

    if az keyvault create \
        --name "$KEY_VAULT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$region" \
        --enable-rbac-authorization true \
        --retention-days 7; then

        _success "Key Vault '$KEY_VAULT_NAME' created"
        _info "Vault URL: $kv_url"
        _info ""
        _info "Next steps:"
        _info "  1. Add to .env.azure: AZURE_KEY_VAULT_URL=$kv_url"
        _info "  2. Grant yourself secrets access: az_kv_grant_access --role officer"
        _info "  3. Grant Batch node identity access: az_kv_grant_access --identity <principalId> --role user"
    else
        _error "Failed to create Key Vault"
        return 1
    fi
}

az_kv_show() {
    _check_kv_env_vars || return 1

    _info "Key Vault: $KEY_VAULT_NAME"

    az keyvault show \
        --name "$KEY_VAULT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "{name: name, location: location, url: properties.vaultUri, rbac: properties.enableRbacAuthorization, state: properties.provisioningState}" \
        -o table
}

az_kv_grant_access() {
    local principal=""
    local role_shorthand="officer"
    local principal_type=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --principal|--identity)
                principal="$2"
                shift 2
                ;;
            --role)
                role_shorthand="$2"
                shift 2
                ;;
            --type)
                principal_type="$2"
                shift 2
                ;;
            *)
                _error "Unknown argument: $1"
                _error "Usage: az_kv_grant_access [--principal <objectId>] [--role officer|user] [--type User|ServicePrincipal]"
                _error "  officer  -> Key Vault Secrets Officer (read + write, for admins)"
                _error "  user     -> Key Vault Secrets User    (read-only, for Batch nodes)"
                _error "  Omit --principal to grant access to the currently signed-in user."
                return 1
                ;;
        esac
    done

    _check_kv_env_vars || return 1

    # Resolve principal — default to current signed-in user
    if [[ -z "$principal" ]]; then
        principal=$(az ad signed-in-user show --query id -o tsv 2>/dev/null)
        if [[ -z "$principal" ]]; then
            _error "Could not resolve current user. Pass --principal <objectId> explicitly."
            return 1
        fi
        _info "Granting access to current signed-in user ($principal)"
        # Default type for signed-in user
        principal_type="${principal_type:-User}"
    else
        # Default type for explicitly provided principal (managed identity)
        principal_type="${principal_type:-ServicePrincipal}"
    fi

    # Map shorthand to full role name
    local role_name
    case "$role_shorthand" in
        officer)
            role_name="Key Vault Secrets Officer"
            ;;
        user)
            role_name="Key Vault Secrets User"
            ;;
        *)
            _error "Unknown role '$role_shorthand'. Use 'officer' or 'user'."
            return 1
            ;;
    esac

    # Get the Key Vault resource ID for scoping the role assignment
    local kv_id
    kv_id=$(az keyvault show \
        --name "$KEY_VAULT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query id -o tsv)

    if [[ -z "$kv_id" ]]; then
        _error "Could not retrieve Key Vault resource ID for '$KEY_VAULT_NAME'"
        return 1
    fi

    _info "Principal:  $principal"
    _info "Type:       $principal_type"
    _info "Role:       $role_name"
    _info "Scope:      $kv_id"

    if az role assignment create \
        --role "$role_name" \
        --assignee-object-id "$principal" \
        --assignee-principal-type "$principal_type" \
        --scope "$kv_id"; then

        _success "Role '$role_name' assigned to $principal"
    else
        _error "Failed to assign role. Ensure you have 'Owner' or 'User Access Administrator' on the vault."
        return 1
    fi
}

az_kv_list_secrets() {
    _check_kv_env_vars || return 1

    _info "Listing secrets in Key Vault: $KEY_VAULT_NAME"

    az keyvault secret list \
        --vault-name "$KEY_VAULT_NAME" \
        --query "[].{name: name, enabled: attributes.enabled, updated: attributes.updated}" \
        -o table
}

#
# Utility Functions
#

az_help() {
    cat << 'EOF'
Azure Batch Helper Functions
=============================

Environment Management:
  az_load_env [file]              Load environment from .env.azure (or specified file)

Pool Management:
  az_pool_create --json <file> [--autoscale] [--yes]         Create pool from JSON config
  az_pool_assign_identity [pool_id]                          Attach managed identity to pool (run after create)
  az_pool_delete [pool_id] [--yes]                           Delete pool (with confirmation)
  az_pool_resize <0|1> [pool_id] [--yes]                     Resize pool to 0 or 1 persistent nodes
  az_pool_update --json <file> [--pool-id <id>] [--autoscale] [--yes]  Update pool configuration
  az_pool_list                                               List all pools
  az_pool_show [pool_id]                                     Show detailed pool information

Node Management:
  az_node_list [pool_id]         List all nodes in pool
  az_node_get_id [pool_id] [idx]  Get node ID (by index, default: 0)
  az_node_logs [pool] [type] [dir] Download start task logs (type: stderr/stdout)

Job Management:
  az_jobs_list                    List all jobs
  az_job_get_latest [pool_id]     Get latest job ID for pool
  az_job_logs [pool_id]           Show tasks for latest job in pool

Storage Management:
  az_storage_upload <src> <dest> [acct] [cont] [--yes]  Upload file to blob storage
  az_storage_download <blob> <dest> [acct] [cont]       Download file from blob storage
  az_storage_list [container] [account]                 List blobs in container

SAS Token Management:
  az_sas_generate <blob> [acct] [cont] [days]   Generate SAS token for blob

Managed Identity Management:
  az_identity_create [--yes]                                Create user-assigned managed identity
  az_identity_show                                          Show identity details (principalId, resourceId)

Key Vault Management:
  az_kv_create [--region <r>] [--yes]                       Create Azure Key Vault
  az_kv_show                                                Show Key Vault details and URL
  az_kv_grant_access [--principal <id>] [--role officer|user]  Assign RBAC role on the vault
  az_kv_list_secrets                                        List secret names in the vault

Nextflow Debugging:
  az_fetch_nf_logs [log_file] [output_dir]   Download all command logs from a Nextflow run

Redis VM Management:
  az_redis_vm_status              Show VM power state and Redis reachability
  az_redis_vm_start [--yes]       Start a deallocated Redis VM
  az_redis_vm_stop [--yes]        Deallocate Redis VM (stops compute billing)
  az_redis_vm_ssh                 Open SSH session to Redis VM

Utility:
  az_help                         Show this help message

Default Values:
  Pool ID: taxodactyl
  Storage Account (std): $STORAGE_ACCOUNT_STD
  Storage Account (prem): $STORAGE_ACCOUNT_PREM
  Container (scripts): $STORAGE_CONTAINER_SCRIPTS

Examples:
  # Load environment
  az_load_env

  # Create pool with autoscaling (interactive)
  az_pool_create --json deployment/azure/pool-setup.json.ignore --autoscale

  # Attach managed identity to pool so nodes can access Key Vault
  az_pool_assign_identity

  # Create pool without autoscaling (non-interactive, for scripts)
  az_pool_create --json deployment/azure/pool-setup.json.ignore --yes

  # Resize pool to 1 node (interactive)
  az_pool_resize 1

  # Resize pool to 0 nodes (non-interactive, for scripts)
  az_pool_resize 0 --yes

  # Get start task logs
  az_node_logs

  # Upload script to blob storage (interactive)
  az_storage_upload deployment/azure/setup.sh setup.sh

  # Upload without confirmation (for scripts)
  az_storage_upload deployment/azure/setup.sh setup.sh --yes

  # Generate SAS token
  az_sas_generate setup.sh

  # Enable autoscaling on default pool (interactive)
  az_pool_update --autoscale

  # Enable autoscaling on specific pool (non-interactive)
  az_pool_update --autoscale --pool-id taxodactyl --yes

  # Enable autoscaling using positional pool ID
  az_pool_update --autoscale taxodactyl

  # Update pool configuration and enable autoscaling
  az_pool_update --json deployment/azure/pool-setup.json.ignore --autoscale

  # Update pool configuration only (non-interactive)
  az_pool_update --json deployment/azure/pool-setup.json.ignore --yes

  # Download all command logs from a workflow run
  az_fetch_nf_logs .nextflow.log.1 ./logs_run1

  # Download logs from the latest run (default)
  az_fetch_nf_logs

  # Create Key Vault (interactive)
  az_kv_create

  # Create Key Vault in a specific region (non-interactive)
  az_kv_create --region australiaeast --yes

  # Show vault details (URL, state, RBAC mode)
  az_kv_show

  # Grant the current signed-in user read+write (officer) access
  az_kv_grant_access --role officer

  # Grant a Batch node managed identity read-only (user) access
  az_kv_grant_access --principal <managed-identity-object-id> --role user

  # List all secret names stored in the vault
  az_kv_list_secrets

  # Create the Batch pool managed identity (reads MANAGED_IDENTITY_NAME from env)
  az_identity_create

  # Show identity details including principalId needed for Key Vault role assignment
  az_identity_show

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
        az_load_env
    else
        _warning "No .env.azure file found in current directory"
        _info "Environment variables not loaded - run 'az_load_env <file>' to load manually"
    fi

    echo ""
    echo -e "${BLUE}Available Commands:${NC}"
    echo ""
    echo "  Pool Management:"
    echo "    az_pool_create, az_pool_assign_identity, az_pool_delete, az_pool_resize"
    echo "    az_pool_update, az_pool_list, az_pool_show"
    echo "    (run az_pool_assign_identity after az_pool_create to attach Key Vault access)"
    echo ""
    echo "  Node Management:"
    echo "    az_node_list, az_node_get_id, az_node_logs"
    echo ""
    echo "  Job Management:"
    echo "    az_jobs_list, az_job_get_latest, az_job_logs"
    echo ""
    echo "  Storage Management:"
    echo "    az_storage_upload, az_storage_download, az_storage_list"
    echo ""
    echo "  SAS Token Management:"
    echo "    az_sas_generate"
    echo ""
    echo "  Nextflow Debugging:"
    echo "    az_fetch_nf_logs"
    echo ""
    echo "  Redis VM Management:"
    echo "    az_redis_vm_status, az_redis_vm_start, az_redis_vm_stop, az_redis_vm_ssh"
    echo "  Managed Identity Management:"
    echo "    az_identity_create, az_identity_show"
    echo ""
    echo "  Key Vault Management:"
    echo "    az_kv_create, az_kv_show, az_kv_grant_access, az_kv_list_secrets"
    echo ""
    echo -e "${GREEN}Run 'az_help' for detailed usage information${NC}"
    echo ""
fi
