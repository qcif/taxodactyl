# Azure Batch Integration Status

## Current Status

We have successfully integrated Nextflow with Azure Batch and achieved working autoscaling. However, we're currently blocked on implementing the start task for reference data staging.

### What's Working

1. **Basic Nextflow execution on Azure Batch**: ✅
   - Workflows run successfully on Azure Batch
   - Tasks execute in Docker containers (docker.io/library/ubuntu:20.04)
   - Container memory set to 1GB (Azure Batch minimum is 6MB, Nextflow defaults to 1MB which causes failures)

2. **Autoscaling**: ✅
   - Successfully configured autoscaling using `$ActiveTasks` metric
   - Formula: `initialNodes=0; maxNodes=1; demand = avg($ActiveTasks.GetSample(TimeInterval_Minute * 1)); $TargetDedicatedNodes = min(max(demand, initialNodes), maxNodes);`
   - Evaluation interval: PT5M (5 minutes minimum)
   - **Important**: `$PendingTasks` does NOT work with Nextflow (always returns 0)
   - **Important**: `$ActiveTasks` only works AFTER tasks start running, not when queued

3. **Pool configuration**: ✅
   - VM size: Standard_L8as_v3 (8 cores, NVMe local storage)
   - Task slots: 8 (matches VM cores)
   - Container image: Ubuntu 20.04 container-enabled (`microsoft-azure-batch/ubuntu-server-container/20-04-lts`)
   - Container whitelist: Must include all Docker images in `containerImageNames` array

### What's NOT Working

1. **Start task for reference data staging**: ❌
   - Start task fails immediately with exit code 1
   - No stderr/stdout logs available
   - Issue 1: Public blob access disabled on storage account, requires SAS token
   - Issue 2: Script (deployment/azure/setup.sh) likely failing due to missing dependencies or environment issues
   - Script expects: azcopy, NVMe device detection, sudo permissions

2. **Autoscaling detection of queued tasks**: ⚠️
   - Autoscaling doesn't detect tasks immediately when submitted
   - Autoscale evaluation runs every 5 minutes
   - Tasks remain queued until evaluation cycle detects `$ActiveTasks`
   - This can cause long delays before nodes are provisioned

## Configuration Files

### deployment/azure/pool.json
Current pool configuration with start task (includes SAS token for setup.sh):
```json
{
  "id": "taxodactyl",
  "vmSize": "standard_l8as_v3",
  "taskSchedulingPolicy": {
    "nodeFillType": "spread"
  },
  "taskSlotsPerNode": 8,
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
        "httpUrl": "https://daffstandard.blob.core.windows.net/scripts/setup.sh?se=REDACTED&sp=r&spr=https&sv=REDACTED&sr=b&sig=REDACTED",
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

**Note**: The SAS token expires on 2026-12-23. Will need to regenerate before then.

### conf/azure.config
Critical settings:
```groovy
process {
    executor = 'azurebatch'
    queue = 'taxodactyl'
    container = 'docker.io/library/ubuntu:20.04'  // Must be fully qualified
    time = '1h'
    memory = '1 GB'  // CRITICAL: Azure Batch requires minimum 6MB
}

azure {
    batch {
        location          = 'australiaeast'
        accountName       = 'daffbatch'
        accountKey        = System.getenv('AZURE_BATCH_ACCESS_KEY')
        poolId            = 'taxodactyl'
        autoPoolMode      = false
        allowPoolCreation = false
        queueOptions      = '--retain 30m'
    }
}
```

## Common Commands

### Load environment variables
```bash
set -a && source .env.azure && set +a
```

### Pool management
```bash
# Delete pool
az batch pool delete \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --yes

# Create pool
az batch pool create \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --json-file deployment/azure/pool.json

# Show pool status
az batch pool show \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --query "{id: id, state: state, dedicated: currentDedicatedNodes, target: targetDedicatedNodes}"

# Resize pool manually
az batch pool resize \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --target-dedicated-nodes 1
```

### Autoscaling
```bash
# Enable autoscaling
az batch pool autoscale enable \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --auto-scale-formula 'initialNodes=0; maxNodes=1; demand = avg($ActiveTasks.GetSample(TimeInterval_Minute * 1)); $TargetDedicatedNodes = min(max(demand, initialNodes), maxNodes);' \
  --auto-scale-evaluation-interval PT5M

# Disable autoscaling
az batch pool autoscale disable \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID

# Check autoscale evaluation
az batch pool show \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --query "{autoScale: enableAutoScale, lastEval: autoScaleRun.timestamp, results: autoScaleRun.results}"
```

### Node inspection
```bash
# List nodes
az batch node list \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --query "[].{id: id, state: state, startTaskState: startTaskInfo.state, startTaskResult: startTaskInfo.result}" \
  -o table

# Get start task failure details
NODE_ID=$(az batch node list \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --query "[0].id" -o tsv)

az batch node list \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --query "[0].startTaskInfo"

# Download start task logs
az batch node file download \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --node-id $NODE_ID \
  --file-path startup/stderr.txt \
  --destination /dev/stdout
```

### Run test workflow
```bash
set -a && source .env.azure && set +a
nextflow run deployment/azure/hello-world.nf -c conf/azure.config
```

### Generate new SAS token for setup.sh
```bash
az storage blob generate-sas \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_SCRIPTS \
  --name setup.sh \
  --permissions r \
  --expiry $(date -u -d "+1 year" '+%Y-%m-%dT%H:%MZ') \
  --https-only \
  --output tsv
```

## Next Tasks

### Immediate Priority: Fix Start Task

1. **Debug setup.sh failure**
   - The script is failing immediately with exit code 1
   - No stderr/stdout logs are being generated
   - Need to simplify the script or add better error logging

2. **Options to investigate**:

   **Option A**: Simplify start task for testing
   - Create a minimal test script that just echoes success
   - Verify SAS token URL is working correctly
   - Add error logging to script (redirect to files that will persist)

   **Option B**: Fix deployment/azure/setup.sh issues
   - Script uses `set -euo pipefail` which exits on first error
   - Likely failing on: azcopy not installed, NVMe device detection, or sudo commands
   - Need to install azcopy or use alternative method
   - Add verbose logging: `set -x` at start of script
   - Check if NVMe device exists and is mounted

   **Option C**: Use alternative approach
   - Instead of start task, mount Azure Files or use blob fuse
   - Stage reference data to blob storage and access directly from tasks
   - Use Nextflow's azure.reference configuration for read-only data

3. **Recommended approach**:
   - First, create a minimal test start task to verify the SAS token and basic execution work
   - Once that succeeds, incrementally add functionality to setup.sh
   - Add comprehensive error logging to each step of setup.sh

### Secondary Priority: Improve Autoscaling

The current autoscaling works but has limitations:

1. **Problem**: 5-minute evaluation interval causes delays
   - Tasks can wait up to 5 minutes before nodes are provisioned
   - This is the minimum allowed by Azure Batch

2. **Problem**: `$ActiveTasks` only detects running tasks, not queued
   - Nextflow submits tasks to Azure Batch as "jobs"
   - Tasks don't show up in `$PendingTasks` metric
   - Only visible in `$ActiveTasks` after they start (but can't start without nodes)

3. **Potential solutions to investigate**:
   - Pre-warm pool with `initialNodes=1` to avoid cold start
   - Use Nextflow's `queueOptions` to tune task submission
   - Consider using fixed pool size instead of autoscaling for production workloads
   - Investigate if there's a way to query Nextflow job queue from autoscale formula

## Key Learnings

### Critical Configuration Requirements

1. **Container memory must be >= 6MB**
   - Azure Batch rejects containers with `--memory 1m` (Nextflow default)
   - Set `memory = '1 GB'` in process configuration

2. **Container images must be fully qualified**
   - Use `docker.io/library/ubuntu:20.04` not `ubuntu:20.04`
   - Add all images to pool's `containerImageNames` array

3. **Ubuntu version matters**
   - Must use Ubuntu 20.04 container image for Docker support
   - Ubuntu 24.04 doesn't support container feature on Azure Batch

4. **Storage account access**
   - Public blob access is disabled on daffstandard storage account
   - Must use SAS tokens for blob URLs in start task resourceFiles
   - SAS tokens have expiration dates (current: 2026-12-23)

5. **Autoscaling formula**
   - Use `$ActiveTasks` not `$PendingTasks`
   - Minimum evaluation interval is PT5M (5 minutes)
   - Formula must use avg() or max() aggregation functions
   - Example: `avg($ActiveTasks.GetSample(TimeInterval_Minute * 1))`

### Start Task Requirements

1. **Script must be accessible via HTTP(S)**
   - Use SAS token if public access is disabled
   - Put SAS token in httpUrl parameter

2. **Script runs with specified userIdentity**
   - Use `elevationLevel: admin` for sudo commands
   - Use `scope: pool` for pool-wide context

3. **waitForSuccess must be true**
   - Prevents tasks from running until start task succeeds
   - Node state will be `starttaskfailed` if script fails

4. **Error handling in scripts**
   - Use `set -x` for verbose logging
   - Avoid `set -e` if you want to handle errors gracefully
   - Redirect output to ensure logs are captured

## Environment Variables

Required in .env.azure:
- `BATCH_ACCOUNT`: daffbatch
- `ACCOUNT_ENDPOINT`: https://daffbatch.australiaeast.batch.azure.com
- `POOL_ID`: taxodactyl
- `AZURE_BATCH_ACCESS_KEY`: (secret)
- `AZURE_STORAGE_ACCOUNT_KEY`: (secret)
- `STORAGE_ACCOUNT_STD`: daffstandard
- `STORAGE_CONTAINER_SCRIPTS`: scripts

## References

- Azure Batch autoscaling documentation: https://learn.microsoft.com/en-us/azure/batch/batch-automatic-scaling
- Nextflow Azure Batch executor: https://www.nextflow.io/docs/latest/azure.html
- Previous session documentation: docs/azure-setup.md
