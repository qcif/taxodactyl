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
  --kind BlockBlobStorage

az storage container create \
  --name $STORAGE_CONTAINER_REF \
  --account-name $STORAGE_ACCOUNT_PREM

# Create standard storage account for work directory and scripts
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
