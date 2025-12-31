# Reference Data Management

This guide covers uploading reference data to Azure blob storage and staging it to compute nodes.

## Overview

Reference data is stored in premium blob storage and staged to each compute node's local NVMe storage during node initialization. This provides:

- **Fast access**: NVMe SSDs offer extremely high IOPS and throughput
- **Cost efficiency**: Premium blob storage billed only for storage, not data transfer within same region
- **Scalability**: Each node gets its own copy, eliminating network bottlenecks

## Storage Structure

**Blob Storage Hierarchy**:
- Premium storage account: `daffpremium`
- Container: `refdata`
- Virtual directory: `core_nt/` (or your reference data name)

**Node Storage Paths**:
- Host path: `/mnt/nvme/refdata/core_nt/` (created by start task)
- Container path: `/mnt/nvme/refdata/core_nt/` (read-only mount)
- Nextflow param: `params.refdata_path = "/mnt/nvme/refdata/core_nt"`

## Uploading Reference Data

### Set Up User Role for azcopy

First, grant yourself permissions to upload blobs:

```sh
# Get your user principal
az login
USER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Assign the "Storage Blob Data Contributor" role
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee "$USER_OBJECT_ID" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_PREM"

# Wait a few minutes for role assignment to propagate
```

### Upload with azcopy

Use azcopy for large data uploads (faster and more reliable than `az storage blob upload-batch`):

```sh
azcopy copy \
  "./core_nt" \
  "https://${STORAGE_ACCOUNT_PREM}.blob.core.windows.net/${STORAGE_CONTAINER_REF}/core_nt/" \
  --recursive \
  --overwrite=ifSourceNewer \
  --log-level INFO
```

**Important**: The blob path should include the virtual directory that matches where Nextflow will expect to find it on the NVMe mount point.

## Staging Reference Data to Nodes

Reference data is automatically staged during node initialization by the start task. See [Start Tasks](04-start-tasks.md) for configuration details.

### Performance Metrics

Our 225GB reference dataset downloads in **2.3 minutes** (~1.6 GB/second) thanks to:
- Premium blob storage with high IOPS
- NVMe local storage (extremely fast writes)
- azcopy's parallel transfer engine
- Optimized settings (no MD5 validation, unlimited bandwidth)

**Measured Performance** (225GB dataset, 429 files):
- **Duration**: 2 minutes 20 seconds
- **Average throughput**: 1.6 GB/second
- **Data transferred**: 241,803,166,593 bytes (225 GB)
- **Files transferred**: 429
- **Failures**: 0

### VM Storage Layout (Standard_L8as_v3)

- `/dev/sdb` (30G): OS disk mounted at `/`
- `/dev/sda` (80G): Temporary storage mounted at `/mnt`
- `/dev/nvme0n1` (1.8T): NVMe local storage (formatted and mounted to `/mnt/nvme`)

**Available space after formatting**: 1.7TB

## Authentication for Reference Data Access

The start task needs access to premium blob storage. You have three options:

### Option 1: SAS Token (Recommended)

Generate a SAS token for the premium blob container:

```sh
# Generate a SAS token with read permission
az storage blob generate-sas \
  --account-name $STORAGE_ACCOUNT_PREM \
  --container-name $STORAGE_CONTAINER_REF \
  --name core_nt \
  --permissions r \
  --expiry $(date -u -d "+1 year" '+%Y-%m-%dT%H:%MZ') \
  --https-only \
  --output tsv
```

Use this token in the start task script's `BLOB_URL`:

```bash
BLOB_URL="https://daffpremium.blob.core.windows.net/refdata/core_nt?<SAS_TOKEN>"
```

### Option 2: Storage Account Key

Set environment variable in start task:

```bash
export AZCOPY_AUTO_LOGIN_TYPE=SPN
# Provide storage account key via secure method
```

### Option 3: Managed Identity

Enable managed identity on Azure Batch nodes (more complex setup).

## Verifying Reference Data

After staging completes, verify the data is accessible:

```sh
# SSH to node (if enabled) or check start task logs
ls -lh /mnt/nvme/refdata/core_nt/
du -sh /mnt/nvme/refdata/core_nt/
```

Expected output:
- 429 files
- 225GB total size

## Troubleshooting

### Reference Data Not Found

1. Check start task logs (see [Troubleshooting](05-troubleshooting.md))
2. Verify blob URL points to correct container/directory
3. Ensure SAS token has not expired
4. Check NVMe mount succeeded in start task

### Slow Download Speed

1. Verify using premium blob storage (not standard)
2. Check azcopy version (`azcopy --version` should be v10.x)
3. Ensure no bandwidth throttling (`--cap-mbps 0`)
4. Verify VM SKU has NVMe storage (L-series)

### Permission Errors

1. Check SAS token permissions include read (`r`)
2. Verify SAS token has not expired
3. Ensure SAS token is properly URL-encoded in BLOB_URL

## Next Steps

- [Configure start tasks for automatic staging](04-start-tasks.md)
- [Troubleshoot common issues](05-troubleshooting.md)
