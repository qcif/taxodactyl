# Plan: Azure Redis (ACI) for Distributed Rate-Limiting

## Context

The Taxodactyl pipeline's `throttle.py` already supports a Redis backend (`RedisQueueBackend`) for distributed rate-limiting across concurrent workflow instances. When running on Azure Batch, multiple Nextflow workflow runs share the same Batch node and rate-limiting state must be coordinated between containerised tasks to avoid hitting API limits (GBIF, NCBI Entrez, BOLD). The SQLite backend is insufficient because each containerised Batch task gets its own filesystem.

Redis needs to be on-demand (not running 24/7), shared across all Batch task containers, and cost-effective (~$0 when idle).

## Architecture: VNet-private ACI with TTL-tag cleanup

Run `redis:7-alpine` as an ACI container group (`daff-redis`) on a private subnet within a new VNet. Lifecycle is managed via an `expiresAt` tag (refreshed on each workflow start) and a cron job on the always-on web server that deletes the ACI when the tag lapses.

**Why this approach:**
- **Private networking**: no public Redis exposure; no password required (though one will still be set)
- **TTL-via-tag**: no `trap`, no `redis-cli` dependency on the orchestrator, no process coordination — the workflow stamps a tag and walks away; crash-tolerant by design
- **"Last write wins"**: concurrent workflows each refresh `expiresAt`; the ACI outlives all of them without coordination
- **Cron cleanup on always-on web server**: reliable runner, no extra Azure services (Automation Account, Logic App, etc.)

---

## Infrastructure Changes (one-time setup)

### 1. VNet and subnets

Create a VNet and two subnets in resource group `daff-biosecurity`, region `australiaeast`:

```bash
az network vnet create \
  --resource-group daff-biosecurity \
  --name daff-vnet \
  --address-prefixes 10.0.0.0/16

az network vnet subnet create \
  --resource-group daff-biosecurity \
  --vnet-name daff-vnet \
  --name aci-subnet \
  --address-prefixes 10.0.1.0/24 \
  --delegations Microsoft.ContainerInstance/containerGroups

az network vnet subnet create \
  --resource-group daff-biosecurity \
  --vnet-name daff-vnet \
  --name batch-subnet \
  --address-prefixes 10.0.2.0/24
```

Optional NSG rule: allow Batch → ACI on TCP 6379.

### 2. Batch pool recreation

The existing `taxodactyl` pool has no VNet. It must be deleted and recreated with `--subnet-id` pointing to `batch-subnet`. This is a one-time disruption — document the current pool config before deleting.

`pool-setup.json.template` gains a `networkConfiguration.subnetId` field.

### 3. Private DNS zone (optional but recommended)

A Private DNS zone (`redis.internal`) resolves `daff-redis.redis.internal` to the ACI's private IP, avoiding the need to query the IP dynamically on each run:

```bash
az network private-dns zone create \
  --resource-group daff-biosecurity \
  --name redis.internal

az network private-dns link vnet create \
  --resource-group daff-biosecurity \
  --zone-name redis.internal \
  --name daff-vnet-link \
  --virtual-network daff-vnet \
  --registration-enabled false
```

An A record pointing `daff-redis` → ACI private IP is created/updated by `az_redis_start`.

---

## Files to Modify

### 1. `deployment/azure/batch-helpers.sh`

Add a new **Redis Management** section (before `az_help`) with constants and functions.

**Constants** (top of file alongside existing defaults):
```bash
REDIS_CONTAINER_GROUP="daff-redis"
REDIS_VNET="daff-vnet"
REDIS_SUBNET="aci-subnet"
REDIS_PORT="6379"
REDIS_CPU="0.5"
REDIS_MEMORY_GB="0.5"
REDIS_DEFAULT_TTL_HOURS="6"   # expiresAt = now + 6h; tune to expected max workflow runtime
```

**Functions:**

`az_redis_start [--ttl-hours N] [--yes]`
- Checks `RESOURCE_GROUP` env var is set
- Computes `expiresAt = $(date -u -d "+N hours" +%s)` (Unix timestamp)
- Queries current container group state via `az container show`
- If **Running**: updates `tags.expiresAt` only (`az container update --set tags.expiresAt=...`) — no restart
- If **not found**: creates ACI in `aci-subnet` with `--ip-address Private`, `--tags expiresAt=... role=ephemeral-redis`, and Redis server command with password, maxmemory, and persistence disabled
- Waits for `Running` state (polls up to 60s)
- If Private DNS is configured: upserts the A record with the ACI's private IP
- Prints private IP and connection info

`az_redis_stop [--yes]`
- Confirms unless `--yes`
- Runs `az container stop` — deallocates compute, preserves container definition for fast restart

`az_redis_delete [--yes]`
- Confirms with strong warning
- Runs `az container delete`

`az_redis_status`
- Shows container state, private IP, `expiresAt` tag (formatted as human-readable datetime), time remaining

`az_redis_ensure_running [--ttl-hours N]`
- Non-interactive `az_redis_start --yes` for use in scripts

`az_redis_cleanup`
- Lists all ACIs tagged `role=ephemeral-redis` in the resource group
- Deletes any where `expiresAt < now - grace_period (5 min)`
- **This is the function called by the cron job on the web server**

`az_redis_ping`
- Uses `redis-cli` (if available) or `nc` to test connectivity
- Note: only reachable from within the VNet (Batch node) or via VPN; documented accordingly

Update the **sourced startup banner** and `az_help` examples.

### 2. `deployment/azure/run-taxodactyl.sh`

After loading `.env.azure`, when `THROTTLE_BACKEND=redis`:

```bash
if [[ "${THROTTLE_BACKEND:-}" == "redis" ]]; then
    source "$(dirname "$0")/batch-helpers.sh" 2>/dev/null
    az_redis_ensure_running --ttl-hours "${REDIS_TTL_HOURS:-6}"
    # Retrieve private IP unless already set (e.g. via Private DNS)
    if [[ -z "${REDIS_HOST:-}" ]]; then
        REDIS_HOST=$(az container show \
            --resource-group "$RESOURCE_GROUP" \
            --name "$REDIS_CONTAINER_GROUP" \
            --query "ipAddress.ip" -o tsv)
        export REDIS_HOST
    fi
fi
```

If Private DNS is configured, `REDIS_HOST=daff-redis.redis.internal` can be set in `.env.azure` and the dynamic lookup is skipped.

Pass `REDIS_HOST` and `REDIS_PORT` into the Nextflow run via env so Batch task containers inherit them.

### 3. `deployment/azure/pool-setup.json.template`

Add `networkConfiguration` block:
```json
"networkConfiguration": {
    "subnetId": "/subscriptions/.../resourceGroups/daff-biosecurity/providers/Microsoft.Network/virtualNetworks/daff-vnet/subnets/batch-subnet"
}
```

### 4. `.env.sample`

Add:
```bash
# Redis (distributed rate-limiting via ACI on private VNet)
THROTTLE_BACKEND=redis
REDIS_PASSWORD="your-strong-redis-password"
REDIS_PORT=6379
REDIS_TTL_HOURS=6
# REDIS_HOST is set dynamically by run-taxodactyl.sh, or hardcode if using Private DNS:
# REDIS_HOST=daff-redis.redis.internal
```

---

## Files to Create

### 5. `docs/azure/07-redis.md`

Document:
- Architecture (ACI on private VNet, TTL-tag lifecycle)
- One-time setup: VNet, subnets, Batch pool recreation, optional Private DNS
- Workflow integration: what `run-taxodactyl.sh` does automatically
- Cleanup cron job setup on the web server (command, recommended interval: 10 min)
- Tuning `REDIS_TTL_HOURS` for expected workflow runtimes
- Troubleshooting: `az_redis_status`, ACI logs, `az_redis_ping` (VNet-only)

### 6. Update `docs/azure/README.md`

Add `7. **[Redis](07-redis.md)**` to the Documentation Index and add Redis helper functions to the helper function listing.

---

## Cron Job (web server)

Add to crontab on the always-on web server:

```cron
*/10 * * * * cd /path/to/wf2-nextflow && source deployment/azure/batch-helpers.sh && az_redis_cleanup
```

Requires: `az` CLI authenticated on the web server (service principal or managed identity), `.env.azure` readable.

---

## Verification

1. `az network vnet list` — confirm `daff-vnet` with both subnets
2. `az_redis_start` — creates ACI, waits for Running, prints private IP
3. `az_redis_status` — shows Running, `expiresAt` ~6h from now
4. Submit a Nextflow run via `run-taxodactyl.sh` — confirm `REDIS_HOST` resolved, Batch tasks connect to Redis
5. `az_redis_cleanup` with an artificially past `expiresAt` tag — confirm ACI is deleted
6. Run cron job on web server — confirm it executes cleanly
7. `az_redis_start` again — confirm recreation completes in ~30–45s
