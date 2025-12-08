# Azure batch setup

First set up a billing account "DASS development", and subscription "DAFF Biosecurity" to contain these resources.

After creating the subscription, it can take an hour or more for the necessary resources to spawn. To wait for them to come online:

```sh
# Wait until this shows "Registered" or you will get "Subscription not found" error when you continue
watch -n 30 'az provider show -n Microsoft.Storage --subscription "DAFF Biosecurity" --query registrationState'
```

## Resources

```sh
SUBSCRIPTION="DAFF Biosecurity"
REGION=australiaeast
RESOURCE_GROUP=daff-biosecurity
STORAGE_ACCOUNT_PREM=daffpremium
STORAGE_ACCOUNT_STD=daffstandard
STORAGE_CONTAINER_REF=refdata
STORAGE_CONTAINER_WORK=workdata
STORAGE_CONTAINER_SCRIPTS=scripts
BATCH_ACCOUNT=daffbatch
POOL_ID=taxodactyl
DEDICATED_NODES=0
NODE_AGENT_SKU="batch.node.ubuntu 20.04"
IMAGE_TAG=Canonical:ubuntu-2404-lts:server:latest
VM_TYPE=Standard_L4s_v3

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

Now get credentials required for NF config:

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

## Managing pools

For development, don't worry about pools and just set NF config as:

```
    batch {
        location = 'australiaeast'
        accountName = 'daffbatch'
        autoPoolMode = true
        allowPoolCreation = true
        vmType = 'Standard_L4s_v3'
        vmCount = 1
        maxNodes = 1
    }
```

This will auto-create a single pool with max one node for each workflow invocation. This means that invocations are completely independent, and have to stage reference data every time (not great for production).

To create and manage a persistent node:

```sh
# Create a pool to submit jobs to
az batch pool create \
  --id $POOL_ID \
  --vm-size $VM_TYPE \
  --node-agent-sku-id $NODE_AGENT_SKU \
  --image $IMAGE_TAG \
  --target-dedicated-nodes $DEDICATED_NODES
```

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

To resize the batch pool in future (e.g. to change the number of persistent nodes):

```sh
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes <int: new node count>
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

Persistent ref data is held on premium blob, where it can be staged to the node's local NVME (est. 5-20 mins) on node spawn. This can be done with a "Start task".

First we must write a shell script that defines our start task (see [deployment/azure/setup.sh](../deployment/azure/setup.sh)) and upload that to our storage account:

```sh
az storage blob upload \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_SCRIPTS \
  --file deployment/azure/setup.sh \
  --name setup.sh
```

Now set the start task for the pool to use this script. We need to define the start task in a JSON file:

```json
// pool.json

{
  "startTask": {
    "commandLine": "/bin/bash setup.sh",
    "resourceFiles": [
      {
        "httpUrl": "https://daffstandard.blob.core.windows.net/scripts/setup.sh",
        "filePath": "start.sh"
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

And then update the pool with this config:

```sh
az batch pool set --pool-id $POOL_ID --json-file spec.json
```

If you want an existing persistent node to use the updated start task, it will need to be re-created:

```sh
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes 0
az batch pool resize --pool-id $POOL_ID --target-dedicated-nodes 1
```
