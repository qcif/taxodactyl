# Plan: Always-On Redis VM for Distributed Rate-Limiting

## Context

Alternative to the ephemeral ACI approach. A small always-on VM running Redis is simpler to set up and operate — no lifecycle management, no cron cleanup job, no TTL tags. The tradeoff is a fixed cost of ~$8.69/month (PAYG) regardless of usage.

## Architecture: Standard_B2ats_v2 VM

> Standard_B2ats_v2 was the best VM I could find that is cheap, available in the australiaeast region, and has quota available

A `Standard_B2ats_v2` VM (2 vCPU, 1GB RAM) running Redis as a systemd service. Redis is small enough that 1GB RAM is comfortable for rate-limiting workloads (token bucket counters only, no large data sets).

**Cost:** ~US$8.69/month

**Tradeoffs vs ephemeral ACI:**
- Simpler: no lifecycle management, no cron job, static `REDIS_HOST` in `.env.azure`
- More expensive when workflows run infrequently (ACI costs $0 when stopped)
- More appropriate when workflows run daily or near-daily

---

## Infrastructure Changes (one-time setup)

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

This gives a stable DNS hostname: `daff-redis.australiaeast.cloudapp.azure.com`

### 2. NSG rule: restrict Redis port

Allow port 6379 inbound only from Azure Batch node IPs (or Azure datacenter range if dynamic):

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

Alternatively, if the Batch pool is placed on a VNet (see `redis-plan.md`), omit the public IP entirely and use a private IP on `batch-subnet`.

### 3. Install and configure Redis

SSH into the VM and run:

```bash
sudo apt update && sudo apt install -y redis-server

# Set password and bind address
sudo sed -i "s/^# requirepass.*/requirepass YOUR_PASSWORD/" /etc/redis/redis.conf
sudo sed -i "s/^bind 127.0.0.1.*/bind 0.0.0.0/" /etc/redis/redis.conf
sudo sed -i "s/^# maxmemory .*/maxmemory 256mb/" /etc/redis/redis.conf
sudo sed -i "s/^# maxmemory-policy.*/maxmemory-policy allkeys-lru/" /etc/redis/redis.conf

# Disable persistence (rate-limit counters don't need to survive reboots)
sudo sed -i "s/^save 900/# save 900/" /etc/redis/redis.conf
sudo sed -i "s/^save 300/# save 300/" /etc/redis/redis.conf
sudo sed -i "s/^save 60/# save 60/" /etc/redis/redis.conf

sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

This configuration can be templated as `deployment/azure/redis-vm-setup.sh` to make it reproducible.

---

## Files to Modify

### 1. `deployment/azure/batch-helpers.sh`

Add a **Redis VM Management** section with lightweight helpers (the VM is always-on, so these are mostly for maintenance):

**Constants:**
```bash
REDIS_VM_NAME="daff-redis-vm"
REDIS_VM_HOST="daff-redis.australiaeast.cloudapp.azure.com"
REDIS_VM_NSG=daff-redis-nsg
REDIS_VM_TYPE=Standard_B2ats_v2
```

**Functions:**

`az_redis_vm_status`
- Runs `az vm show` to display power state, public IP, and DNS hostname
- Shows whether Redis process is reachable via `nc`

`az_redis_vm_start [--yes]`
- Starts a deallocated VM: `az vm start`
- For use after manual `az_redis_vm_stop` (maintenance)

`az_redis_vm_stop [--yes]`
- Deallocates the VM: `az vm deallocate`
- Frees compute cost while preserving OS disk
- Warning: Redis will be unavailable until restarted

`az_redis_vm_ssh`
- Opens an SSH session to the VM for maintenance

### 2. `.env.azure.sample`

Add:
```bash
# Redis VM (always-on, distributed rate-limiting)
THROTTLE_BACKEND=redis
REDIS_HOST=daff-redis.australiaeast.cloudapp.azure.com
REDIS_PORT=6379
REDIS_PASSWORD="your-strong-redis-password"
```

### 3. `deployment/azure/run-taxodactyl.sh`

No changes needed for lifecycle — `REDIS_HOST` is static. Optionally add a pre-flight check:

```bash
if [[ "${THROTTLE_BACKEND:-}" == "redis" ]] && [[ -n "${REDIS_HOST:-}" ]]; then
    if ! nc -z -w3 "$REDIS_HOST" "${REDIS_PORT:-6379}" 2>/dev/null; then
        echo -e "${YELLOW}WARNING: Redis at $REDIS_HOST:$REDIS_PORT is unreachable${NC}"
    fi
fi
```

---

## Files to Create

### 4. `deployment/azure/redis-vm-setup.sh`

Idempotent setup script to run on the VM after creation. Installs Redis, applies configuration, enables systemd service. Can be re-run safely for config updates.

### 5. `docs/azure/07-redis.md`

- VM creation and Redis setup steps
- NSG configuration
- Connection from Batch nodes
- Maintenance: SSH access, config changes, `az_redis_vm_stop`/`start` for planned downtime
- Monitoring: `az_redis_vm_status`

---

## Verification

1. `az_redis_vm_status` — shows Running, prints hostname
2. `redis-cli -h daff-redis.australiaeast.cloudapp.azure.com -p 6379 -a $REDIS_PASSWORD ping` → `PONG`
3. Set `.env.azure` with `THROTTLE_BACKEND=redis`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
4. Run `deployment/azure/run-taxodactyl.sh` — Batch tasks connect to Redis successfully
5. `az_redis_vm_stop` then `az_redis_vm_start` — confirm Redis recovers correctly
