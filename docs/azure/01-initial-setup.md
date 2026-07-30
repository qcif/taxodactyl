# Azure Initial Setup

This guide covers creating the Azure resources needed to run Taxodactyl workflows on Azure Batch.

## Prerequisites

- Azure CLI installed and configured
- Access to create resources in your Azure subscription
- Sufficient permissions to request quota increases

>[!NOTE]
> Run `source deployment/azure/batch-helpers.sh` to get a load of functions to ease your interactions with the azure CLI.

## Step 1: Subscription Setup

First, set up a billing account and subscription to contain these resources.

After creating the subscription, it can take an hour or more for the necessary resources to spawn. To wait for them to come online:

```sh
# Wait until this shows "Registered" or you will get "Subscription not found" error when you continue
watch -n 30 'az provider show -n Microsoft.Storage --subscription "DAFF Biosecurity" --query registrationState'
```

## Step 2: Create Azure Resources

Create all required Azure resources:

```sh
# Add these vars to a .env.azure file for quick reference like:
# $ set -a && source .env.azure && set +a
SUBSCRIPTION="DAFF Biosecurity"
REGION=australiaeast
RESOURCE_GROUP=daff-biosecurity
STORAGE_ACCOUNT_PREM=daffpremium
STORAGE_ACCOUNT_STD=daffstandard
STORAGE_CONTAINER_REF=refdata
STORAGE_CONTAINER_WORK=workdata
STORAGE_CONTAINER_SCRIPTS=scripts
STORAGE_CONTAINER_CACHE=cache
BATCH_ACCOUNT=daffbatch
ACCOUNT_ENDPOINT=daffbatch.australiaeast.batch.azure.com
POOL_ID=taxodactyl
DEDICATED_NODES=0
NODE_AGENT_SKU="batch.node.ubuntu 20.04"
IMAGE_TAG=canonical:ubuntu-20_04-lts:server
VM_SKU=Standard_L8as_v3
VM_CPUS=8

# Set active subscription
az account set --subscription "$SUBSCRIPTION"

# Create resource group
az group create -n $RESOURCE_GROUP -l $REGION

# Create premium storage account for reference data
az storage account create \
  -n $STORAGE_ACCOUNT_PREM \
  -g $RESOURCE_GROUP \
  -l $REGION \
  --sku Premium_LRS \
  --kind BlockBlobStorage \
  --allow-blob-public-access true

az storage container create \
  --name $STORAGE_CONTAINER_REF \
  --account-name $STORAGE_ACCOUNT_PREM \
  --public-access blob

# Create standard storage account for work directory and scripts
az storage account create \
  -n $STORAGE_ACCOUNT_STD \
  -g $RESOURCE_GROUP \
  -l $REGION \
  --sku Standard_LRS \
  --allow-blob-public-access true

az storage container create \
  --name $STORAGE_CONTAINER_WORK \
  --account-name $STORAGE_ACCOUNT_STD

az storage container create \
  --name $STORAGE_CONTAINER_SCRIPTS \
  --account-name $STORAGE_ACCOUNT_STD \
  --public-access blob

# Create the cache container used by the API-response cache
# (shared across all Batch nodes; see Step 3b below for the
# connection string that the workflow uses to authenticate).
az storage container create \
  --name $STORAGE_CONTAINER_CACHE \
  --account-name $STORAGE_ACCOUNT_STD

# Create batch account
az batch account create \
  --name $BATCH_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $REGION \
  --storage-account $STORAGE_ACCOUNT_STD
```

Optionally, you can set a storage policy on the work container.
We have written one that results in work data being retained for 14 days only:

```sh
az storage account management-policy create \
  --account-name $STORAGE_ACCOUNT_STD \
  --resource-group $RESOURCE_GROUP \
  --policy deployment/azure/storage-policy.json
```

> [!NOTE]
> The provided storage policy also includes a rule that deletes blobs in
> the `$STORAGE_CONTAINER_CACHE` container after `cache_timeout_hours`
> has elapsed. The cache backend does a best-effort delete on read of
> expired entries, but the lifecycle rule is what actually garbage
> collects entries that are never read again. Make sure the rule's
> "days after modification" value is at least as large as
> `CACHE_TIMEOUT_HOURS / 24` (default 7 days).


## Step 3: Get Credentials

Retrieve credentials required for Nextflow configuration:

```sh
az batch account login \
  --name daffbatch \
  --resource-group daff-biosecurity \
  --shared-key-auth

# These should be saved in 1Password/DevOps and added to .env.azure:
az storage account keys list -g daff-biosecurity -n daffstandard
az storage account keys list -g daff-biosecurity -n daffpremium
az batch account keys list -g daff-biosecurity -n daffbatch
```

Add these to your `.env.azure` file:

```bash
AZURE_BATCH_ACCOUNT_NAME=daffbatch
AZURE_BATCH_ACCESS_KEY=<primary_key>
AZURE_BATCH_ENDPOINT=https://daffbatch.australiaeast.batch.azure.com
AZURE_STORAGE_ACCOUNT_KEY=<standard_storage_key>
NXF_AZURE_REFERENCE_KEY=<premium_storage_key>
```

### Step 3b: Cache Connection String

The workflow's API-response cache uses the `$STORAGE_CONTAINER_CACHE`
container in `$STORAGE_ACCOUNT_STD` and authenticates via a connection
string that the Python code reads from the
`CACHE_AZURE_CONNECTION_STRING` environment variable. You have two
options for generating it — an **account-key** connection string
(simplest, full data-plane access to the entire account) or a
**container-scoped SAS** connection string (least privilege, recommended
for production).

#### Option A: Account-key connection string (simplest)

This gives the cache client read/write access to the whole storage
account. Fine for development; for production prefer Option B.

```sh
CACHE_AZURE_CONNECTION_STRING=$(
  az storage account show-connection-string \
    -g $RESOURCE_GROUP \
    -n $STORAGE_ACCOUNT_STD \
    --query connectionString -o tsv
)
echo "CACHE_AZURE_CONNECTION_STRING=$CACHE_AZURE_CONNECTION_STRING"
```

The resulting string looks like:

```
DefaultEndpointsProtocol=https;AccountName=daffstandard;AccountKey=...;EndpointSuffix=core.windows.net
```

#### Option B: Container-scoped SAS connection string (least privilege)

This produces a connection string that only grants read/write/delete/list
permissions on the single `$STORAGE_CONTAINER_CACHE` container, with an
expiry date. Rotate it before it expires.

```sh
# Pick an expiry date (1 year here) and obtain the account key.
EXPIRY=$(date -u -d '1 year' '+%Y-%m-%dT%H:%MZ')
ACCOUNT_KEY=$(
  az storage account keys list \
    -g $RESOURCE_GROUP \
    -n $STORAGE_ACCOUNT_STD \
    --query '[0].value' -o tsv
)

# Generate a container-scoped SAS token with the permissions the
# cache backend needs:
#   r = read (download blobs)
#   w = write (upload blobs)
#   d = delete (expire stale blobs)
#   l = list (optional, useful for maintenance/debugging)
#   c = create (first-use blob creation)
SAS_TOKEN=$(
  az storage container generate-sas \
    --account-name $STORAGE_ACCOUNT_STD \
    --account-key "$ACCOUNT_KEY" \
    --name $STORAGE_CONTAINER_CACHE \
    --permissions rwdlc \
    --expiry "$EXPIRY" \
    --https-only \
    -o tsv
)

# Assemble the connection string. Note this uses BlobEndpoint +
# SharedAccessSignature (not AccountKey), which is how the Azure SDK
# distinguishes SAS-based connection strings.
CACHE_AZURE_CONNECTION_STRING="BlobEndpoint=https://${STORAGE_ACCOUNT_STD}.blob.core.windows.net;SharedAccessSignature=${SAS_TOKEN}"
echo "CACHE_AZURE_CONNECTION_STRING=$CACHE_AZURE_CONNECTION_STRING"
```

> [!NOTE]
> With a container-scoped SAS the client will receive `403` on any
> attempt to `create_container()`, because the SAS has no account-level
> permissions. The cache backend catches this error and continues, as
> long as the container already exists (which it does, having been
> created above). Just make sure to re-run Option B before the `EXPIRY`
> date passes, or the workflow will start logging put/get failures.

#### Store it in `.env.azure`

Regardless of which option you picked, add the result to `.env.azure`
alongside the other credentials:

```bash
# Cache container details (consumed by the scripts/src/utils/cache.py
# AzureBlobCacheBackend at runtime)
CACHE_BACKEND=azure_blob
CACHE_AZURE_CONTAINER=cache
CACHE_AZURE_CONNECTION_STRING='<paste value from above>'
```

The Batch pool start task should inject these same three variables into
every task's environment so that workers on ephemeral nodes share a
single cache. See [04-start-tasks.md](04-start-tasks.md) for where to
wire this in.

## Step 4: Set Batch Account Quota

New subscriptions start with zero pools in the Batch account quota and zero quota for specific VM SKUs. You'll need to request a quota increase through the Azure portal.

[Request quota increase via Azure Portal](https://learn.microsoft.com/en-us/azure/quotas/quickstart-increase-quota-portal)

### Manual Process

1. Sign into Azure Portal
2. Search for "quotas"
3. Click on "request a quota increase"
4. Quota type: "Batch" (click Next)
5. Enter your details in the form, and click "Enter details"
6. Fill out the form
7. "Select quotas to update":
   - "LS series" (or your chosen VM series)
   - "Pools per Batch account"
8. Enter a new (reasonable) limit for each of the above
9. Save and continue
10. Wait for your request to be approved

**Note**: The VM series that you want to use may not be listed in the quota request form. You may need to ask for it in a support ticket after determining which SKUs are available in your region.

### Checking Available VM SKUs

To list available VM SKUs in your region:

```sh
az batch location list-skus --location $REGION
```

## Next Steps

Once your Azure resources are created and quotas approved:

1. [Create and manage batch pools](02-pool-management.md)
2. [Upload and stage reference data](03-reference-data.md)
3. [Configure start tasks](04-start-tasks.md)
