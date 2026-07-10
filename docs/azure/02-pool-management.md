# Pool Management

This guide covers creating and managing Azure Batch pools for running Taxodactyl workflows.

## Important Note About Pools

Since our workflow requires reference data, **do not use Nextflow's `autoPoolMode`**. We need to set up the pool with a start task to stage reference data for each node spawn event. If Nextflow creates its own pool, there won't be any reference data there!

## Managed Identity for Key Vault Access

> [!NOTE]
> Azure Key Vault is optional, but can be used to remember the user's API key and facility. You can also use local key vault by setting a SECRET_KEY, or leave it out entirely to disable this feature.

Batch nodes authenticate to Azure Key Vault using a **user-assigned managed identity**
attached to the pool. This allows tasks to call `DefaultAzureCredential()` without any
secrets or passwords being baked into the pool configuration.

### Create the managed identity

Set `MANAGED_IDENTITY_NAME` in `.env.azure`, then:

```sh
az_load_env
az_identity_create
```

Or with the raw Azure CLI:

```sh
az identity create \
  --name "$MANAGED_IDENTITY_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$REGION"
```

Note the `principalId` and full `id` (resource ID) from the output — you need both below.

### Grant the identity access to Key Vault

```sh
# Use the principalId from the step above
az_kv_grant_access --principal <principalId> --role officer
```

This assigns the `Key Vault Secrets User` role (read-only) to the identity on the vault.
See [07-key-vault.md](07-key-vault.md) for vault creation instructions if you haven't
done that yet.

### Attach the identity to the pool

> [!NOTE]
> The Batch Service REST API (used by `az batch pool create`) does not accept the
> `identity` field. The identity must be patched onto the pool via the ARM API
> **after** creation.

Once the pool exists, run:

```sh
az_pool_assign_identity
```

This uses `MANAGED_IDENTITY_NAME`, `RESOURCE_GROUP`, and `AZURE_BATCH_ACCOUNT_NAME`
from your environment to PATCH the pool's ARM resource. The identity can be added to
an existing pool without recreating it.

## Creating a Development Pool

For development, we create a pool with autoscaling to minimize costs while maintaining quick access to compute resources.

### Pool Configuration

First, create a JSON file to define the pool resources. We use Ubuntu 20.04 for Docker container compatibility:

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
  }
}
```

**Note**: Some properties (`vmSize`, `targetDedicatedNodes`) can only be provided at pool creation, not when updating. To modify these, you'll need to delete and re-create the pool.

### Create the Pool

```sh
# Load environment variables
set -a && source .env.azure && set +a

# Create pool
az batch pool create \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --id $POOL_ID \
  --vm-size $VM_SKU \
  --node-agent-sku-id "$NODE_AGENT_SKU" \
  --image $IMAGE_TAG \
  --json-file deployment/azure/pool.json
```

**Helper equivalent:** `az_pool_create deployment/azure/pool.json`

If using Key Vault, attach the managed identity after the pool is created:

```sh
az_pool_assign_identity
```

### Enable Autoscaling

Configure the pool to automatically scale based on workload:

```sh
az batch pool autoscale enable \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --auto-scale-formula '
    initialNodes=0;
    maxNodes=1;
    demand = avg($ActiveTasks.GetSample(TimeInterval_Minute * 1));
    $TargetDedicatedNodes = min(max(demand, initialNodes), maxNodes);' \
  --auto-scale-evaluation-interval PT5M
```

Read more about [autoscale formulas](https://learn.microsoft.com/en-us/azure/batch/batch-automatic-scaling).

**Important Limitations**:
- `$ActiveTasks` only detects RUNNING tasks, not queued tasks
- `$PendingTasks` always returns 0 for Nextflow-submitted tasks
- Autoscale evaluation interval minimum: 5 minutes
- Tasks can wait up to 5 minutes before nodes are provisioned

### Configure Nextflow

Configure Nextflow to submit jobs to the pool (in `conf/azure.config`):

```groovy
batch {
  location          = 'australiaeast'
  accountName       = 'daffbatch'
  poolId            = 'taxodactyl'
  autoPoolMode      = false
  allowPoolCreation = false

  // Keep nodes warm for 30 minutes after tasks complete:
  queueOptions      = '--retain 30m'
}
```

This allows you to benefit from re-using staged reference data between workflow runs without needing to manually manage node shutdown.

## Persistent Nodes (Production)

For production workloads, persistent nodes eliminate the 10-15 minute staging time on each job submission, at the cost of continuous billing.

### Create a Persistent Pool

```sh
# Create a pool with persistent nodes
az batch pool create \
  --id $POOL_ID \
  --vm-size $VM_SKU \
  --node-agent-sku-id "$NODE_AGENT_SKU" \
  --image $IMAGE_TAG \
  --target-dedicated-nodes $DEDICATED_NODES
```

**Warning**: A persistent node will stay alive until manual shutdown and will continue billing at the machine's hourly rate. Don't forget to shut it down!

### Configure Nextflow for Persistent Nodes

```groovy
batch {
  location          = 'australiaeast'
  accountName       = 'daffbatch'
  poolId            = 'taxodactyl'
  autoPoolMode      = false
  allowPoolCreation = false
}
```

For higher throughput, increase the number of nodes (with linear cost increase).

## Pool Management Commands

### Resize a Pool

```sh
# Scale up
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes <int: new node count>

# Scale down to zero (terminate all nodes)
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes 0
```

**Helper equivalent:** `az_pool_resize 1` or `az_pool_resize 0`

### Re-create Nodes

To force a configuration update:

```sh
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes 0
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes <int: new node count>
```

**Helper equivalent:** `az_pool_resize 0 --yes && az_pool_resize 1`

### View Pool Status

Check current node count:

```sh
az batch pool show \
  --account-name "$BATCH_ACCOUNT" \
  --account-endpoint "$ACCOUNT_ENDPOINT" \
  --pool-id "$POOL_ID" \
  --query "{
    dedicated: currentDedicatedNodes,
    lowPriority: currentLowPriorityNodes,
    resizing: resizeOperationStatus
  }"
```

**Helper equivalent:** `az_pool_show`

List all pools with configuration:

```sh
az batch pool list \
  --account-name "$BATCH_ACCOUNT" \
  --account-endpoint "$ACCOUNT_ENDPOINT" \
  --query "[].{id: id, vmSize: vmSize, taskSlotsPerNode: taskSlotsPerNode}"
```

**Helper equivalent:** `az_pool_list`

View running tasks:

```sh
az batch pool list \
  --account-name "$BATCH_ACCOUNT" \
  --account-endpoint "$ACCOUNT_ENDPOINT" \
  --query "[].{id: id, state: state, vmSize: vmSize, runningTasks: runningTasksCount, startTime: nodeAgentInfo.lastUpdateTime}"
```

**Helper equivalent:** `az_pool_list` (shows running tasks)

### Delete a Pool

If everything goes wrong and you need to delete the pool:

```sh
az batch pool delete \
  --account-name "$BATCH_ACCOUNT" \
  --account-endpoint "$ACCOUNT_ENDPOINT" \
  --pool-id "$POOL_ID"
```

**Helper equivalent:** `az_pool_delete`

## Next Steps

- [Upload and stage reference data](03-reference-data.md)
- [Configure start tasks](04-start-tasks.md)
