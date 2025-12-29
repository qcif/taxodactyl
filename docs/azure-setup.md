# Azure batch setup

First set up a billing account "DASS development", and subscription "DAFF Biosecurity" to contain these resources.

After creating the subscription, it can take an hour or more for the necessary resources to spawn. To wait for them to come online:

```sh
# Wait until this shows "Registered" or you will get "Subscription not found" error when you continue
watch -n 30 'az provider show -n Microsoft.Storage --subscription "DAFF Biosecurity" --query registrationState'
```

## Resources

```sh
# Add these vars to a .env.azure file for quick reference like:
# $ set -a && source .env && set +a
SUBSCRIPTION="DAFF Biosecurity"
REGION=australiaeast
RESOURCE_GROUP=daff-biosecurity
STORAGE_ACCOUNT_PREM=daffpremium
STORAGE_ACCOUNT_STD=daffstandard
STORAGE_CONTAINER_REF=refdata
STORAGE_CONTAINER_WORK=workdata
STORAGE_CONTAINER_SCRIPTS=scripts
BATCH_ACCOUNT=daffbatch
ACCOUNT_ENDPOINT=daffbatch.australiaeast.batch.azure.com
POOL_ID=taxodactyl
DEDICATED_NODES=0
NODE_AGENT_SKU="batch.node.ubuntu 20.04"
IMAGE_TAG=canonical:ubuntu-20_04-lts:server
VM_SKU=Standard_L8as_v3
VM_CPUS=8

az account set --subscription "$SUBSCRIPTION"
az group create -n $RESOURCE_GROUP -l $REGION
az storage account create \
  -n $STORAGE_ACCOUNT_PREM \
  -g $RESOURCE_GROUP \
  -l $REGION \
  --sku Premium_LRS \
  --kind BlockBlobStorage
az storage container create \
  --name $STORAGE_CONTAINER_REF \
  --account-name $STORAGE_ACCOUNT_PREM
az storage account create \
  -n $STORAGE_ACCOUNT_STD \
  -g $RESOURCE_GROUP \
  -l $REGION \
  --sku Standard_LRS
az storage container create \
  --name $STORAGE_CONTAINER_WORK \
  --account-name $STORAGE_ACCOUNT_STD
az storage container create \
  --name $STORAGE_CONTAINER_SCRIPTS \
  --account-name $STORAGE_ACCOUNT_STD
az batch account create \
  --name $BATCH_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $REGION \
  --storage-account $STORAGE_ACCOUNT_STD
```

Now let's get credentials required for NF config:

```sh
az batch account login \
  --name daffbatch \
  --resource-group daff-biosecurity \
  --shared-key-auth

# These have been saved in 1Password/DevOps:
az storage account keys list -g daff-biosecurity -n daffstandard
az storage account keys list -g daff-biosecurity -n daffpremium
az batch account keys list -g daff-biosecurity -n daffbatch
```

## Set batch account quota

Now, finally set a reasonable resource quota on the batch account. New
subscriptions start with zero pools in the Batch account quota, as this is
considered a high risk resource by Azure (I guess you can run up a huge bill if
you aren't careful). There will also probably be zero quota for the VM SKU that you want to use (probably an L series).
I couldn't find a reliable way to do this over the CLI so had to
[do this manually on the
Azure portal](https://learn.microsoft.com/en-us/azure/quotas/quickstart-increase-quota-portal).

(In case you can't find the right page, I went through the following at [this horrible URL](https://portal.azure.com/#@qcif.edu.au/resource/subscriptions/73d25025-7bc9-44f5-a163-3727fc0121a8/resourceGroups/daff-biosecurity/providers/Microsoft.Batch/batchAccounts/daffbatch/accountQuotas))

1. Sign into Azure Portal
1. Search for "quotas"
1. Click on "request a quota increase"
1. Quota type: "Batch" (click Next)
1. Enter your details in the form, and click "Enter details"
1. Fill out the form
1. "Select quotas to update":
  - "LS series" (or your chosen VM series)
  - "Pools per Batch account"
1. Enter a new (reasonable) limit for each of the above (don't put 100 unless you want to pay for that!)
1. Save and continue
1. Wait for your request to be approved? (mine was eventually approved after some deliberation on what SKUs are actually available in Australia East region)

>[!NOTE]
>The VM series that I decided to use was (confusingly) not listed in the quota request form. I had to ask for it in a support ticket, after some deliberating over what SKUs are currently available in my region.

## Managing pools

For development, we can create a pool and submit jobs with a "keep warm" option
to ensure that nodes do not have to be re-staged between job/process
submissions.

>[!NOTE]
>Since our workflow requires reference data, it's important that we don't use
>Nextflow's `autoPoolMode`, because we have to set up the pool to stage ref
>data for each node spawn event. If Nextflow creates its own pool, there won't
>be any reference data there!

[az pool docs](https://learn.microsoft.com/en-us/cli/azure/batch/pool?view=azure-cli-latest)

Let's start by creating a pool for development. This first requires a JSON file to be written which defines the pool resources. We have to use Ubuntu 20.04 for Docker container compatibility:

```json
// pool.json

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
>[!NOTE]
>Some of the properties above (vmSize, targetDedicatedNodes) can only be provided at pool create, not when updating a pool with pool set. If these need to be modified, you'll need to delete and re-create the pool.

>[!NOTE]
>N.B. I haven't yet discovered whether Nextflow's containers will also need to be added to `containerImageNames`. I imagine they probably will - for example when running BLAST, an `ncbi/blast` image will replace the `ubuntu:20.04` image used for testing above.

Now we can use this config to create a pool:

```sh
az batch pool create \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --id $POOL_ID \
  --vm-size $VM_SKU \
  --node-agent-sku-id "$NODE_AGENT_SKU" \
  --image $IMAGE_TAG \
  --json-file deployment/azure/pool.json

# Autoscale the nodes to spawn one only when a job is in the queue (note this is NOT the same as autopool)
az batch pool autoscale enable \
  --account-name $BATCH_ACCOUNT \
  --account-endpoint $ACCOUNT_ENDPOINT \
  --pool-id $POOL_ID \
  --auto-scale-formula '
    initialNodes=0;
    maxNodes=1;
    demand =
      avg($ActiveTasks.GetSample(TimeInterval_Minute * 1));
    $TargetDedicatedNodes = min(max(demand, initialNodes), maxNodes);' \
  --auto-scale-evaluation-interval PT5M
```

(Read about the [autoscale formula](https://learn.microsoft.com/en-us/azure/batch/batch-automatic-scaling))

To list available VM SKUs:

```sh
az batch location list-skus --location $REGION
```

To show provisioned vmsize/slots for pools in the batch account:

```sh
az batch pool list \
  --account-name "$BATCH_ACCOUNT" \
  --account-endpoint "$ACCOUNT_ENDPOINT" \
  --query "[].{id: id, vmSize: vmSize, taskSlotsPerNode: taskSlotsPerNode}"
```

Or to see running tasks (including queued):

```sh
az batch pool list \
  --account-name "$BATCH_ACCOUNT" \
  --account-endpoint "$ACCOUNT_ENDPOINT" \
  --query "[].{id: id, state: state, vmSize: vmSize, runningTasks: runningTasksCount, startTime: nodeAgentInfo.lastUpdateTime}"
```

And now configure Nextflow to submit jobs to that pool:

```
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

This way, we can benefit from re-using staged ref data between workflow runs,
but don't need to worry about shutting down the node when we're done for the
day.

### Persistent nodes

For production, a persistent node is a more expensive option that eliminates
staging time (15 mins) on the node for each job. To create and manage a
persistent node:

```sh
# Create a pool to submit jobs to
az batch pool create \
  --id $POOL_ID \
  --vm-size $VM_SKU \
  --node-agent-sku-id "$NODE_AGENT_SKU" \
  --image $IMAGE_TAG \
  --target-dedicated-nodes $DEDICATED_NODES
```

>[!WARNING]
>Warning: a persistent node will stay alive until manual shutdown. During this
>time the instance will continue billing to your account at the machine's
>hourly rate. Don't forget to shut it down!

Then we can force Nextflow to send jobs to the persistent node with:

```
  batch {
      location = 'australiaeast'
      accountName = 'daffbatch'
      poolId = 'taxodactyl'
      autoPoolMode = false
      allowPoolCreation = false
  }
```

For higher throughput, the number of nodes could be increased (with a linear
cost increase).

To resize the batch pool in future (e.g. to change the number of persistent nodes):

```sh
# To terminate all nodes, just set the target to zero
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes <int: new node count>
```

To re-create the node (e.g. to force config update):

```sh
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes 0
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes <int: new node count>
```

To see what nodes are currently active in the pool:

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

If everything goes horribly wrong, and you want to delete the pool (and any nodes that are consuming $$$):

```sh
az batch pool delete \
  --account-name "$BATCH_ACCOUNT" \
  --account-endpoint "$ACCOUNT_ENDPOINT" \
  --pool-id "$POOL_ID"
```


## Uploading reference data

Before anything can be run, we need to upload our reference data to premium blob storage container, with a specific structure to ensure that the start task and workflow can find the expected files. The blob path we upload to here should include the virtual dir that matches where Nextflow will expect to find it in the NVME mount point, where it will eventually be staged.

For large data uploads, azcopy is faster and more reliable than `az storage blob upload-batch` .


### Set up user role for azcopy

```sh
# Get your user principal
az login
USER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Assign the "Blob Data Contributor" role
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee "$USER_OBJECT_ID" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_PREM"

# Wait a few minutes to propagate

azcopy copy \
  "./core_nt" \
  "https://${STORAGE_ACCOUNT_PREM}.blob.core.windows.net/${STORAGE_CONTAINER_REF}/core_nt/" \
  --recursive \
  --overwrite=ifSourceNewer \
  --log-level INFO
```

## Staging reference data

Persistent ref data is held on premium blob, where it can be staged to the node's local NVME on node spawn. This can be done with a "Start task".

**Performance**: Our 225GB reference dataset downloads in **2.3 minutes** (~1.6 GB/second) thanks to:
- Premium blob storage
- NVMe local storage (high write speed)
- azcopy's parallel transfers
- Optimized settings (no MD5 validation, unlimited bandwidth)

### Uploading the Start Task Script

First we must write a shell script that defines our start task (see [deployment/azure/setup.sh](../deployment/azure/setup.sh)) and upload that to our storage account.

**Authentication**: The `az storage blob upload` command requires authentication. We use the storage account key method:

1. Ensure `AZURE_STORAGE_ACCOUNT_KEY` is set in `.env.azure` (or the environment)
2. The Azure CLI will automatically use this key for authentication

```sh
# Upload the setup script to blob storage
# Note: --overwrite ensures the script is updated if it already exists
az storage blob upload \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_SCRIPTS \
  --file deployment/azure/setup.sh \
  --name setup.sh \
  --overwrite
```

**Important**: If you see warnings about credentials, you can either:
- Set `AZURE_STORAGE_ACCOUNT_KEY` environment variable (recommended for automation)
- Use `--connection-string` parameter with the full connection string
- Use `--auth-mode login` for Azure AD authentication (requires RBAC roles)

### Generating SAS Token for Start Task

Since our storage account has public blob access disabled (for security), we need to create a SAS (Shared Access Signature) token for the start task script. This token allows Azure Batch nodes to download the script.

**SAS Token Requirements:**
- **Permissions**: Read only (`r`)
- **Protocol**: HTTPS only (required by Azure Batch)
- **Expiry**: Set far enough in future (e.g., 1 year)
- **Output**: TSV format for easy copying

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

# Example output (this is what you'll use in the next section):
# se=2026-12-29T04%3A33Z&sp=r&spr=https&sv=2022-11-02&sr=b&sig=RsDV8g%2FRxSXe6Pn2PvGXYqf6bPR27UrX%2BSFhn4SVPxk%3D
```

**Important Notes:**
- The SAS token expires on the date specified in `--expiry`
- Keep the SAS token secure - anyone with this token can read the blob
- You'll need to regenerate the token before expiry and update your pool configuration
- The token is URL-encoded and ready to append to the blob URL

### Configuring the Pool Start Task

Now set the start task for the pool to use this script. We need to define the start task in a JSON file.

**Important**: The httpUrl must include the full SAS token as a query parameter. Replace `<SAS_TOKEN>` with the actual token generated above.

```json
// Add this to pool.json (or create a separate file like pool-setup-sas-token.json)

{
  "id": "taxodactyl",
  "vmSize": "standard_l8as_v3",
  ... (other pool configuration) ...
  "startTask": {
    "commandLine": "/bin/bash setup.sh",
    "resourceFiles": [
      {
        "httpUrl": "https://daffstandard.blob.core.windows.net/scripts/setup.sh?<SAS_TOKEN>",
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

**Key Configuration Points:**
- `commandLine`: The command to execute (runs the downloaded script)
- `resourceFiles[].httpUrl`: Full URL including SAS token query parameters
- `resourceFiles[].filePath`: Where the file will be downloaded on the node
- `waitForSuccess`: Prevents tasks from running until start task succeeds
- `userIdentity.elevationLevel: "admin"`: Gives the script root privileges
- `userIdentity.scope: "pool"`: Script runs in pool context

**Security Note**: Since the SAS token is sensitive, store pool configuration files containing tokens in a gitignored location (e.g., `pool-setup-sas-token.json`). Never commit SAS tokens to version control.

>[!NOTE]
>Any config that we apply with `--json-file` overwrites the existing config. Make sure that you append this to your existing config if you already have a pool.json file for this pool.

And then update the pool with this config:

```sh
az batch pool set --pool-id $POOL_ID --json-file pool.json
```

If you want an existing persistent node to use the updated start task, it will need to be re-created:

```sh
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes 0
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes 1
```

## Start Task Implementation Notes

### What's Working

The start task ([deployment/azure/setup.sh](../deployment/azure/setup.sh)) successfully:

1. **Detects NVMe device**: Identifies `/dev/nvme0n1` (1.8TB) on Standard_L8as_v3 VMs
2. **Formats and mounts NVMe**: Creates ext4 filesystem and mounts to `/mnt/nvme` (1.7TB available)
3. **Creates directory structure**: Sets up `/mnt/nvme/refdata` for reference data
4. **Comprehensive logging**: All output goes to stderr for debugging via `startup/stderr.txt`
5. **Runs as root**: Script executes with admin privileges (no sudo needed)

### Key Learnings

**Script execution environment:**
- Working directory: `/mnt/batch/tasks/startup/wd`
- User: `root` (with admin elevation level)
- Logs available at: `startup/stdout.txt` and `startup/stderr.txt`

**NVMe detection:**
- Device appears as `/dev/nvme0n1` (block device)
- Character device `/dev/nvme0` also exists
- `lsblk` successfully detects it as type "disk"
- Fallback detection using `-b /dev/nvme0n1` works if lsblk fails

**Storage layout on Standard_L8as_v3:**
- `/dev/sdb` (30G): OS disk mounted at `/`
- `/dev/sda` (80G): Temporary storage mounted at `/mnt`
- `/dev/nvme0n1` (1.8T): NVMe local storage (needs formatting/mounting)

**Debugging tips:**
- Use `set -x` for verbose command logging (goes to stderr)
- Redirect informational messages to stderr: `echo "message" >&2`
- Start task fails fast with `set -euo pipefail`
- Download logs with: `az batch node file download --file-path startup/stderr.txt`

### azcopy Installation (Implemented)

The updated [deployment/azure/setup.sh](../deployment/azure/setup.sh) now includes automatic azcopy installation in the `install_azcopy()` function.

**How it works:**
1. Checks if azcopy is already installed (skips installation on warm nodes)
2. Downloads the latest azcopy from Microsoft's CDN
3. Extracts and installs to `/usr/local/bin/`
4. Makes the binary executable
5. Cleans up temporary files

**Primary installation method** (lightweight and fast):
```bash
wget -q -O azcopy.tar.gz https://aka.ms/downloadazcopy-v10-linux
tar -xf azcopy.tar.gz --strip-components=1
mv azcopy /usr/local/bin/
chmod +x /usr/local/bin/azcopy
rm -f azcopy.tar.gz
```

**Alternative method** (commented out, available as fallback):
The script includes a commented-out alternative that uses apt package manager. This can be uncommented if the primary method fails:
```bash
# Install via apt (requires more time for package updates)
wget https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb
dpkg -i packages-microsoft-prod.deb
apt-get update
apt-get install azcopy -y
```

### Reference Data Download (Implemented)

The `stage_refdata()` function now:

1. **Checks for existing data**: Skips download if `/mnt/nvme/refdata` already contains files (warm nodes)
2. **Uses azcopy for download**: Fast, parallel downloads from premium blob storage
3. **Optimized for performance**:
   - `--recursive`: Downloads entire directory structure
   - `--check-md5 NoCheck`: Skips MD5 validation for maximum speed
   - `--cap-mbps 0`: Unlimited bandwidth (no throttling)
4. **Reports progress**: Shows download size and directory listing after completion

**Measured Performance** (225GB dataset, 429 files):
- **Duration**: 2 minutes 20 seconds (2.33 minutes)
- **Average throughput**: 1.6 GB/second
- **Breakdown**:
  - Start time: 05:57:25 UTC
  - End time: 05:59:45 UTC
  - Data transferred: 241,803,166,593 bytes (225 GB)
  - Files transferred: 429
  - Failures: 0

This exceptional performance is achieved through:
- Premium blob storage with high IOPS
- Standard_L8as_v3 VM with NVMe SSD (extremely fast local writes)
- azcopy's parallel transfer engine
- No bottlenecks from MD5 validation or bandwidth throttling

**Authentication for azcopy:**
The `BLOB_URL` in the script points to premium blob storage. For azcopy to access private blob storage, you need one of:
- **SAS token in URL** (recommended): Append SAS token to `BLOB_URL`
- **Storage account key**: Set `AZCOPY_AUTO_LOGIN_TYPE=SPN` and provide credentials
- **Managed identity**: If Azure Batch nodes have managed identity enabled

**Example with SAS token:**
```bash
BLOB_URL="https://daffpremium.blob.core.windows.net/refdata?<SAS_TOKEN>"
```

**Note**: The BLOB_URL should point to the container or directory path, not a non-existent subdirectory. For example:
- ✅ `https://daffpremium.blob.core.windows.net/refdata` (container root)
- ✅ `https://daffpremium.blob.core.windows.net/refdata/core_nt` (specific directory)
- ❌ `https://daffpremium.blob.core.windows.net/refdata/data` (if 'data' directory doesn't exist)

### Accessing Start Task Logs

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
```
