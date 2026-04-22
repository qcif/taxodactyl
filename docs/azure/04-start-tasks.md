# Start Tasks

This guide covers configuring Azure Batch start tasks for node initialization and reference data staging.

## Overview

A start task is a script that runs automatically when a node is provisioned. We use it to:

1. Detect and format the NVMe storage device
2. Mount NVMe to `/mnt/nvme`
3. Install azcopy
4. Download reference data from premium blob storage
5. Verify the setup completed successfully

## Start Task Script

The start task script is located at [deployment/azure/setup.sh](../../deployment/azure/setup.sh).

### What the Script Does

1. **NVMe Detection and Formatting**:
   - Detects `/dev/nvme0n1` (1.8TB on Standard_L8as_v3)
   - Creates ext4 filesystem
   - Mounts to `/mnt/nvme` (1.7TB available)

2. **Directory Structure**:
   - Creates `/mnt/nvme/refdata` for reference data

3. **azcopy Installation**:
   - Downloads latest azcopy from Microsoft CDN
   - Installs to `/usr/local/bin/`
   - Makes executable

4. **Reference Data Download**:
   - Uses azcopy for parallel downloads
   - Optimized for maximum performance
   - Skips if data already exists (warm nodes)

5. **Logging**:
   - All output redirected to stderr
   - Verbose logging with `set -x`
   - Available at `startup/stderr.txt`

### Script Execution Environment

- **Working directory**: `/mnt/batch/tasks/startup/wd`
- **User**: `root` (with admin elevation level)
- **Logs**: `startup/stdout.txt` and `startup/stderr.txt`

## Uploading the Start Task Script

Upload the script to standard blob storage:

```sh
# Load environment variables
set -a && source .env.azure && set +a

# Upload the setup script to blob storage
az storage blob upload \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_SCRIPTS \
  --file deployment/azure/setup.sh \
  --name setup.sh \
  --overwrite
```

**Helper equivalent:** `az_storage_upload deployment/azure/setup.sh setup.sh`

**Authentication**: Requires `AZURE_STORAGE_ACCOUNT_KEY` set in environment or `.env.azure`.

## Generating SAS Tokens

Since storage accounts have public blob access disabled (for security), create SAS tokens for:

1. **Start task script** (standard storage)
2. **Reference data** (premium storage)

### Start Task Script SAS Token

```sh
# Generate a SAS token with read permission
az storage blob generate-sas \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_SCRIPTS \
  --name setup.sh \
  --permissions r \
  --expiry $(date -u -d "+1 year" '+%Y-%m-%dT%H:%MZ') \
  --https-only \
  --output tsv
```

**Helper equivalent:** `az_sas_generate setup.sh`

### Reference Data SAS Token

```sh
# Generate a SAS token for the refdata container
az storage container generate-sas \
  --account-name $STORAGE_ACCOUNT_PREM \
  --name $STORAGE_CONTAINER_REF \
  --permissions r \
  --expiry $(date -u -d "+1 year" '+%Y-%m-%dT%H:%MZ') \
  --https-only \
  --output tsv
```

**Note**: For container-level SAS tokens, use the `az` command above (not available in helpers).

**Important Notes**:
- Keep SAS tokens secure - anyone with the token can access the blob
- Tokens expire on the date specified in `--expiry`
- Regenerate tokens before expiry and update pool configuration
- Never commit SAS tokens to version control

## Configuring the Pool Start Task

Create a pool configuration JSON file with the start task:

```json
{
  "id": "taxodactyl",
  "vmSize": "standard_l8as_v3",
  "taskSchedulingPolicy": {
    "nodeFillType": "spread"
  },
  "taskSlotsPerNode": 8,
  "targetDedicatedNodes": 0,
  "virtualMachineConfiguration": {
    "imageReference": {
      "publisher": "microsoft-azure-batch",
      "offer": "ubuntu-server-container",
      "sku": "20-04-lts"
    },
    "nodeAgentSKUId": "batch.node.ubuntu 20.04",
    "containerConfiguration": {
      "type": "dockerCompatible",
      "containerImageNames": [
        "docker.io/library/ubuntu:20.04"
      ]
    }
  },
  "startTask": {
    "commandLine": "/bin/bash setup.sh",
    "resourceFiles": [
      {
        "httpUrl": "https://daffstandard.blob.core.windows.net/scripts/setup.sh?<SETUP_SCRIPT_SAS_TOKEN>",
        "filePath": "setup.sh"
      }
    ],
    "waitForSuccess": true,
    "userIdentity": {
      "autoUser": {
        "scope": "pool",
        "elevationLevel": "admin"
      }
    }
  }
}
```

**Key Configuration Points**:
- `commandLine`: Command to execute (runs the downloaded script)
- `resourceFiles[].httpUrl`: Full URL including SAS token query parameters
- `resourceFiles[].filePath`: Where the file is downloaded on the node
- `waitForSuccess`: Prevents tasks from running until start task succeeds
- `userIdentity.elevationLevel: "admin"`: Gives script root privileges
- `userIdentity.scope: "pool"`: Script runs in pool context

### Update the Start Task Script with SAS Token

Edit `deployment/azure/setup.sh.ignore` (gitignored file) to include the reference data SAS token:

```bash
BLOB_URL="https://daffpremium.blob.core.windows.net/refdata/core_nt?<REFDATA_SAS_TOKEN>"
```

**Security Pattern**:
- `*.ignore` files: contain actual SAS tokens (gitignored)
- `*.template` files: contain placeholders (version controlled)

## Applying the Configuration

Update the pool with the new configuration:

```sh
az batch pool set --pool-id $POOL_ID --json-file pool-setup.json.ignore
```

**Helper equivalent:** `az_pool_update pool-setup.json.ignore`

**Note**: `--json-file` overwrites the existing configuration. Make sure your file includes all desired settings.

### Force Configuration Update

To force existing nodes to use the updated start task:

```sh
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes 0
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes 1
```

**Helper equivalent:** `az_pool_resize 0 --yes && az_pool_resize 1`

## Accessing Start Task Logs

To debug start task issues:

```bash
# Get node ID
NODE_ID=$(az batch node list \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --query "[0].id" -o tsv)

# Check start task status
az batch node list \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --query "[].{id: id, state: state, startTaskState: startTaskInfo.state, startTaskResult: startTaskInfo.result, exitCode: startTaskInfo.exitCode}" \
  -o table

# Download stderr (main output with set -x enabled)
az batch node file download \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --node-id $NODE_ID \
  --file-path startup/stderr.txt \
  --destination /tmp/start-task-stderr.txt

# Download stdout (filesystem creation output)
az batch node file download \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --node-id $NODE_ID \
  --file-path startup/stdout.txt \
  --destination /tmp/start-task-stdout.txt

# View the logs
cat /tmp/start-task-stderr.txt
```

**Helper equivalent:** `az_node_logs` (downloads and displays stderr) or `az_node_logs taxodactyl stdout` (for stdout)

## Debugging Tips

- Use `set -x` for verbose command logging (goes to stderr)
- Redirect informational messages to stderr: `echo "message" >&2`
- Start task fails fast with `set -euo pipefail`
- Check node state should be `idle` and start task state should be `completed`

## Performance Notes

**Reference Data Staging** (225GB dataset):
- **Time**: 2.3 minutes
- **Throughput**: 1.6 GB/second
- **Source**: Premium blob storage → NVMe SSD
- **Tool**: azcopy v10.31.0

**azcopy Optimization**:
- `--recursive`: Downloads entire directory structure
- `--check-md5 NoCheck`: Skips MD5 validation for maximum speed
- `--cap-mbps 0`: Unlimited bandwidth (no throttling)

## Next Steps

- [Troubleshoot common issues](05-troubleshooting.md)
- [Run workflows on Azure Batch](../../deployment/azure/status.md)
