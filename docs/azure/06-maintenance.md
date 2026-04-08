# Azure Maintenance

This guide covers recurring maintenance tasks for the Taxodactyl Azure
deployment. These are things that don't come up during normal operation
but must be performed periodically to keep the workflow running.

## Table of Contents

- [SAS Token Rotation](#sas-token-rotation)
- [Cache Container Maintenance](#cache-container-maintenance)
- [Storage Account Key Rotation](#storage-account-key-rotation)
- [Lifecycle Policy Review](#lifecycle-policy-review)

## SAS Token Rotation

Several components authenticate to Azure Storage using SAS (Shared
Access Signature) tokens generated during
[initial setup](01-initial-setup.md). SAS tokens have a fixed expiry
date and **will stop working when they expire**, so you need to
rotate them on a schedule.

### What needs rotating

| Token | Where it's configured | Step in initial setup |
|---|---|---|
| Cache container SAS connection string | `.env.azure` → `CACHE_AZURE_CONNECTION_STRING` | [Step 3b, Option B](01-initial-setup.md#step-3b-cache-connection-string) |
| Reference data SAS URLs | Pool start task config | [Reference Data](03-reference-data.md) |

> [!TIP]
> Set a calendar reminder for **one month before** each token's expiry
> so you have time to rotate without downtime. The commands below use a
> 1-year expiry by default.

### Rotating the cache SAS connection string

This is the most common rotation since the cache container SAS is used
by every workflow invocation. The procedure below regenerates the SAS,
updates `.env.azure`, and (if your Batch pool has a start task that
sets the env var) refreshes the start task.

#### 1. Generate a new SAS connection string

Use the exact same commands as Option B in
[Step 3b](01-initial-setup.md#option-b-container-scoped-sas-connection-string-least-privilege),
but pick a fresh expiry date:

```sh
# Load the standard env vars.
set -a && source .env.azure && set +a

# Pick a new expiry (1 year from now).
EXPIRY=$(date -u -d '1 year' '+%Y-%m-%dT%H:%MZ')
echo "New SAS will expire: $EXPIRY"

# Fetch the account key (or use the secondary key if you're mid-rotation;
# see below under "Storage Account Key Rotation").
ACCOUNT_KEY=$(
  az storage account keys list \
    -g $RESOURCE_GROUP \
    -n $STORAGE_ACCOUNT_STD \
    --query '[0].value' -o tsv
)

# Generate the new SAS token.
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

# Assemble the new connection string.
NEW_CONN_STR="BlobEndpoint=https://${STORAGE_ACCOUNT_STD}.blob.core.windows.net;SharedAccessSignature=${SAS_TOKEN}"
echo "New CACHE_AZURE_CONNECTION_STRING=$NEW_CONN_STR"
```

#### 2. Verify the new SAS works before switching

Test the new SAS independently before replacing the old one. A quick
roundtrip with `az storage blob upload`/`download` is enough:

```sh
TEST_FILE=$(mktemp)
echo "sas-rotation-test-$(date +%s)" > "$TEST_FILE"

# Upload with the new SAS.
az storage blob upload \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_CACHE \
  --name "_sas-rotation-probe" \
  --file "$TEST_FILE" \
  --sas-token "$SAS_TOKEN" \
  --overwrite

# Download to verify read access.
az storage blob download \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_CACHE \
  --name "_sas-rotation-probe" \
  --file "${TEST_FILE}.out" \
  --sas-token "$SAS_TOKEN"

diff "$TEST_FILE" "${TEST_FILE}.out" && echo "SAS OK"

# Clean up the probe blob.
az storage blob delete \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_CACHE \
  --name "_sas-rotation-probe" \
  --sas-token "$SAS_TOKEN"

rm -f "$TEST_FILE" "${TEST_FILE}.out"
```

If any of those commands fail, do **not** proceed — re-check the
permissions (`rwdlc`) and expiry date on the SAS and regenerate.

#### 3. Update `.env.azure`

Replace the old `CACHE_AZURE_CONNECTION_STRING` line with the new
value:

```sh
# Back up first.
cp .env.azure .env.azure.bak

# Edit in place. Use your preferred editor instead if you like.
sed -i "s|^CACHE_AZURE_CONNECTION_STRING=.*|CACHE_AZURE_CONNECTION_STRING='${NEW_CONN_STR}'|" .env.azure
```

Verify:

```sh
grep '^CACHE_AZURE_CONNECTION_STRING=' .env.azure
```

#### 4. Update the Batch pool start task (if applicable)

If your pool's start task sets `CACHE_AZURE_CONNECTION_STRING` as an
environment variable for tasks (see
[04-start-tasks.md](04-start-tasks.md)), you need to update the pool
config so new nodes pick up the new value. Nodes that are already
running will keep the old SAS in their environment until they're
recycled.

```sh
# Update the pool's start task env vars (see 04-start-tasks.md for
# the full command - typically az batch pool patch with the updated
# start-task JSON).
az_pool_update deployment/azure/pool-config.json
```

Recycling existing nodes forces them to re-run the start task and
pick up the new SAS:

```sh
# List nodes, then reboot each one.
az batch node list --pool-id $POOL_ID --query "[].id" -o tsv | \
  while read NODE_ID; do
    az batch node reboot --pool-id $POOL_ID --node-id "$NODE_ID"
  done
```

If your pool autoscales down to zero between jobs, you can skip the
reboot step — the next fresh node will use the updated start task
automatically.

#### 5. Verify end-to-end

Run a small test job (e.g. the `P5 DB coverage` launch config against
a single query) with the new env file loaded and watch the logs for
`Azure blob cache` errors. If the run completes without cache-related
warnings, the rotation is done.

#### 6. Secure the old value

- Update 1Password / DevOps / wherever you store the connection string.
- Delete `.env.azure.bak` once you're confident the new value works.
- The old SAS remains technically valid until its original `se=`
  expiry. If you suspect the old value was leaked, rotate the
  **storage account key** (see below) — that invalidates every SAS
  derived from it, old and new.

## Cache Container Maintenance

### Clearing the cache

Occasionally you may want to wipe the Azure blob cache entirely — for
example, if you've changed the cache-key schema, if stale entries are
serving incorrect data, or if you want a clean run for benchmarking.

```sh
# Dry run - list what would be deleted.
az storage blob list \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_CACHE \
  --auth-mode login \
  --query "[].name" -o tsv | head

# Delete all blobs in the cache container.
az storage blob delete-batch \
  --account-name $STORAGE_ACCOUNT_STD \
  --source $STORAGE_CONTAINER_CACHE \
  --auth-mode login
```

> [!WARNING]
> `delete-batch` is irreversible. There is no soft-delete unless you
> have enabled blob soft-delete on the storage account. For
> production, consider enabling soft-delete with a short retention
> (e.g. 7 days) to protect against accidental wipes.

### Checking cache size and object count

```sh
# Count blobs in the cache container.
az storage blob list \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_CACHE \
  --auth-mode login \
  --query "length(@)"

# Sum total bytes stored.
az storage blob list \
  --account-name $STORAGE_ACCOUNT_STD \
  --container-name $STORAGE_CONTAINER_CACHE \
  --auth-mode login \
  --query "[].properties.contentLength" -o tsv | \
  awk '{s+=$1} END {printf "%.2f MB\n", s/1024/1024}'
```

If either number is climbing unexpectedly, check that the lifecycle
rule from [deployment/azure/storage-policy.json](../../deployment/azure/storage-policy.json)
is still enabled (see [Lifecycle Policy Review](#lifecycle-policy-review)).

## Storage Account Key Rotation

The storage account has two access keys (`key1`, `key2`) precisely so
that you can rotate without downtime. Follow this schedule at least
every 90 days, or immediately if you suspect a key has been exposed.

> [!IMPORTANT]
> **Rotating a storage account key invalidates every SAS token that
> was generated from it.** Plan SAS rotations to happen as part of the
> key rotation, or use the "dual key" trick below to avoid it.

### Zero-downtime rotation procedure

1. **Switch all consumers to `key2`** first.
   - Regenerate the cache SAS using `key2`:
     ```sh
     ACCOUNT_KEY=$(
       az storage account keys list \
         -g $RESOURCE_GROUP \
         -n $STORAGE_ACCOUNT_STD \
         --query '[1].value' -o tsv
     )
     # ...then run the SAS generation commands from the rotation
     # section above.
     ```
   - Update `.env.azure`, redeploy, and verify end-to-end as per the
     SAS rotation procedure.

2. **Regenerate `key1`:**
   ```sh
   az storage account keys renew \
     -g $RESOURCE_GROUP \
     -n $STORAGE_ACCOUNT_STD \
     --key key1
   ```

3. **Wait until you're confident nothing is still using the old
   `key1`** (check Azure Monitor / Storage logs for any
   `AuthenticationFailed` errors on the account).

4. **Next rotation cycle**: repeat the procedure in reverse — move
   consumers back to `key1`, then regenerate `key2`.

Repeat `STORAGE_ACCOUNT_PREM` separately for the premium account that
hosts reference data.

## Lifecycle Policy Review

The lifecycle rules defined in
[deployment/azure/storage-policy.json](../../deployment/azure/storage-policy.json)
silently clean up old work files and expired cache entries. Review
them periodically:

```sh
# Show the currently active policy on the standard storage account.
az storage account management-policy show \
  --account-name $STORAGE_ACCOUNT_STD \
  --resource-group $RESOURCE_GROUP
```

Check that:

- The `delete-old-work-files` rule is enabled and its
  `daysAfterModificationGreaterThan` matches your current retention
  requirement (default 14 days).
- The `delete-expired-cache-entries` rule is enabled and its
  `daysAfterModificationGreaterThan` is `>=` `CACHE_TIMEOUT_HOURS / 24`
  (default `CACHE_TIMEOUT_HOURS=168` → 7 days). If you have bumped
  `CACHE_TIMEOUT_HOURS` higher in `.env.azure`, bump the lifecycle
  value to match or the rule will evict entries the workflow still
  considers fresh.

If the rule config in the JSON file has drifted from what's deployed,
re-apply it:

```sh
az storage account management-policy create \
  --account-name $STORAGE_ACCOUNT_STD \
  --resource-group $RESOURCE_GROUP \
  --policy deployment/azure/storage-policy.json
```

> [!NOTE]
> Lifecycle rules run once per day on Azure's internal schedule, so
> expect up to ~24h of lag between a TTL expiring and the blob
> actually disappearing. This is harmless: the cache backend already
> returns `None` for expired entries regardless of whether the blob
> has been physically deleted.
