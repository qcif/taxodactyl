# Redis VM for Distributed Rate-Limiting

Taxodactyl enforces API rate limits (GBIF, NCBI Entrez, BOLD) using a token bucket algorithm in `scripts/src/utils/throttle.py`. When multiple workflow instances run concurrently on the same Azure Batch node, they need to share rate-limiting state — a single Redis instance coordinates this across all containers.

## Deployment options

Two deployment strategies have been evaluated:

| | Always-on VM (current) | On-demand ACI |
|---|---|---|
| **Cost** | ~$8.69/month fixed | ~$0.03/hr running, $0 idle |
| **Complexity** | Low — static hostname, no lifecycle management | Higher — VNet, cron cleanup, dynamic IP |
| **Best for** | Daily or near-daily workflow use | Infrequent use |

The always-on VM approach is currently deployed and documented below. The on-demand ACI approach (ephemeral Redis via Azure Container Instances on a private VNet, with TTL-tag lifecycle management) is documented in [deployment/azure/redis-on-demand-plan.md](../../deployment/azure/redis-on-demand-plan.md) for reference if a lower-cost alternative is needed in future.

## Architecture

A small always-on VM (`Standard_B2ats_v2`, 2 vCPU / 1 GB RAM) runs Redis as a systemd service. Batch task containers connect to it over its public IP, which is restricted by an NSG to accept connections only from within Azure's datacenter range.

**Cost:** ~US$8.69/month

**Why not Azure Cache for Redis?** The Basic tier starts at ~$16/month and is always-on. The VM approach is cheaper and gives full control over the Redis configuration.

## One-Time Setup

These steps are already complete for the `daff-biosecurity` environment. They are documented here for reference and disaster recovery.

### 1. Create the VM

```bash
az vm create \
  --resource-group daff-biosecurity \
  --name daff-redis-vm \
  --image Ubuntu2204 \
  --size Standard_B2ats_v2 \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --public-ip-address-dns-name daff-redis \
  --nsg daff-redis-nsg
```

Stable DNS hostname: `daff-redis.australiaeast.cloudapp.azure.com`

### 2. Restrict the Redis port

```bash
az network nsg rule create \
  --resource-group daff-biosecurity \
  --nsg-name daff-redis-nsg \
  --name allow-redis \
  --priority 100 \
  --protocol Tcp \
  --destination-port-ranges 6379 \
  --source-address-prefixes AzureCloud \
  --access Allow
```

This allows port 6379 from Azure's datacenter IP ranges only. Connections from outside Azure are blocked.

### 3. Install and configure Redis

Set `REDIS_PASSWORD` in your shell, then pipe the setup script to the VM:

```bash
export REDIS_PASSWORD="your-password"
ssh azureuser@daff-redis.australiaeast.cloudapp.azure.com \
    "REDIS_PASSWORD=$REDIS_PASSWORD bash -s" < deployment/azure/redis-vm-setup.sh
```

The setup script (`deployment/azure/redis-vm-setup.sh`) is idempotent and can be re-run if configuration needs to be updated.

## Configuration

Add the following to `.env.azure` (see `.env.azure.sample`):

```bash
THROTTLE_BACKEND=redis
REDIS_HOST=daff-redis.australiaeast.cloudapp.azure.com
REDIS_PORT=6379
REDIS_PASSWORD="your-password"
```

When `THROTTLE_BACKEND=redis` is set, `run-taxodactyl.sh` will verify Redis is reachable before submitting the workflow. If it is not reachable, the script will exit with an error rather than falling back to SQLite.

## Helper Functions

```bash
source deployment/azure/batch-helpers.sh

# Check VM state and Redis reachability
az_redis_vm_status

# Start a stopped VM (e.g. after planned maintenance)
az_redis_vm_start

# Deallocate VM to stop billing (Redis will be unavailable)
az_redis_vm_stop

# SSH into the VM for maintenance
az_redis_vm_ssh
```

## Maintenance

### Updating the Redis password

1. SSH into the VM: `az_redis_vm_ssh`
2. Edit `/etc/redis/redis.conf` and update the `requirepass` line
3. `sudo systemctl restart redis-server`
4. Update `REDIS_PASSWORD` in `.env.azure` on all machines that run workflows

Alternatively, re-run the setup script with the new password:

```bash
export REDIS_PASSWORD="new-password"
ssh azureuser@daff-redis.australiaeast.cloudapp.azure.com \
    "REDIS_PASSWORD=$REDIS_PASSWORD bash -s" < deployment/azure/redis-vm-setup.sh
```

### Planned downtime

```bash
az_redis_vm_stop    # deallocates VM, stops billing
# ... maintenance ...
az_redis_vm_start   # restarts VM, Redis auto-starts via systemd
```

### Checking Redis logs

```bash
az_redis_vm_ssh
sudo journalctl -u redis-server -f
```

## Troubleshooting

**`run-taxodactyl.sh` reports Redis unreachable**

1. `az_redis_vm_status` — check VM power state
2. If deallocated: `az_redis_vm_start`
3. If running but not reachable: `az_redis_vm_ssh` then `sudo systemctl status redis-server`

**Rate-limiting not coordinating between instances**

Verify `THROTTLE_BACKEND=redis` is set in `.env.azure` and the containers are receiving `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD` as environment variables. Check `scripts/src/utils/throttle.py` for which env vars are read.

**Manually testing connectivity from a Batch node**

SSH into the node and run:

```bash
redis-cli -h daff-redis.australiaeast.cloudapp.azure.com -p 6379 -a "$REDIS_PASSWORD" --no-auth-warning ping
```
