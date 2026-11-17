# Reference Data Management

This guide covers uploading reference data to Azure blob storage and staging it to compute nodes.

Required reference data is documented in [README.md](../../../README.md)

## Overview

Reference data (Core Nt and the NCBI taxdump) is stored in the public
`refdata-wf2` container of the standard storage account and staged to each
compute node's local NVMe storage during node initialization. This provides:

- **Fast access**: NVMe SSDs offer extremely high IOPS and throughput
- **Simple access**: the container is public (read-only), so the start task
  needs no credentials
- **Scalability**: Each node gets its own copy, eliminating network bottlenecks

## Storage Structure

**Blob Storage Hierarchy**:
- Storage account: `daffstandard` (`$STORAGE_ACCOUNT_STD`)
- Container: `refdata-wf2` (`$STORAGE_CONTAINER_REF`), public container-level read
- `core_nt/`: the BLAST database (`core_nt.*` volumes and index files,
  `taxdb.*`, `taxonomy4blast.sqlite3` and `checksums/`)
- `taxdump/taxdump/`: the NCBI taxdump (`*.dmp` files)

> [!WARNING]
> Anyone can list and read this container. Only public NCBI reference data
> may be stored in it.

**Node Storage Paths**:
- The start task downloads the container to `/mnt/nvme/refdata-wf2` and
  renames it to `/mnt/nvme/refdata`, so node paths stay `/mnt/nvme/refdata/...`
- Host path: `/mnt/nvme/refdata/` (created by start task)
- Container path: `/mnt/nvme/refdata/` (read-only mount)
- Pipeline params (set in `deployment/azure/run-taxodactyl.sh`):
  - `--blastdb /mnt/nvme/refdata/core_nt/core_nt`
  - `--taxdb /mnt/nvme/refdata/taxdump/taxdump`

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
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_STD"

# Wait a few minutes for role assignment to propagate
```

### Upload with azcopy

Use azcopy for large data uploads (faster and more reliable than `az storage blob upload-batch`):

```sh
cd $REFDATA/blast/core_nt/
azcopy copy \
  './*' \
  "https://${STORAGE_ACCOUNT_STD}.blob.core.windows.net/${STORAGE_CONTAINER_REF}/core_nt/" \
  --recursive \
  --overwrite=ifSourceNewer \
  --log-level INFO

cd $REFDATA/taxonkit/
azcopy copy \
  './*' \
  "https://${STORAGE_ACCOUNT_STD}.blob.core.windows.net/${STORAGE_CONTAINER_REF}/taxdump/" \
  --recursive   \
  --overwrite=ifSourceNewer   \
  --log-level INFO
```

Uploading requires authenticated write access (the role above); only reads
are anonymous.

**Important**: The blob path should include the virtual directory that matches where Nextflow will expect to find it on the NVMe mount point.

## Staging Reference Data to Nodes

Reference data is automatically staged during node initialization by the start task. See [Start Tasks](04-start-tasks.md) for configuration details.

### Performance Metrics

> These figures were measured on the earlier premium-storage setup.

Our 225GB reference dataset downloads in **2.3 minutes** (~1.6 GB/second) thanks to:
- Blob storage with high throughput
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

## Access

Downloads are anonymous: the container has public container-level access, so
there is no token to generate or rotate. To check anonymous access:

```sh
azcopy list "https://daffstandard.blob.core.windows.net/refdata-wf2"
```

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
2. Verify `BLOB_URL` in `deployment/azure/setup.sh.template` points to the
   `refdata-wf2` container
3. Check NVMe mount succeeded in start task

### Slow Download Speed

1. Check azcopy version (`azcopy --version` should be v10.x)
2. Ensure no bandwidth throttling (`--cap-mbps 0`)
3. Verify VM SKU has NVMe storage (L-series)

### Permission Errors

1. Check the container's public access level is `container`:
   ```sh
   az storage container show-permission \
     --name $STORAGE_CONTAINER_REF \
     --account-name $STORAGE_ACCOUNT_STD
   ```
2. Check the storage account still allows public blob access
   (`az storage account show -n $STORAGE_ACCOUNT_STD --query allowBlobPublicAccess`)

## Next Steps

- [Configure start tasks for automatic staging](04-start-tasks.md)
- [Troubleshoot common issues](05-troubleshooting.md)
