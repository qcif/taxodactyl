#!/bin/bash
#
# Redis VM Setup Script
#
# Run this script on the daff-redis-vm after creation to install and configure
# Redis for distributed rate-limiting. Safe to re-run for config updates.
#
# Usage (from your local machine):
#   ssh azureuser@daff-redis.australiaeast.cloudapp.azure.com \
#       'bash -s' < deployment/azure/redis-vm-setup.sh
#
# Or after SSH-ing in:
#   bash redis-vm-setup.sh
#

set -euo pipefail

REDIS_CONF="/etc/redis/redis.conf"
MAXMEMORY="256mb"

if [[ -z "${REDIS_PASSWORD:-}" ]]; then
    echo "ERROR: REDIS_PASSWORD environment variable is not set"
    echo "Export it before running: export REDIS_PASSWORD=your-password"
    exit 1
fi

echo "=== Installing Redis ==="
sudo apt-get update -qq
sudo apt-get install -y redis-server

echo ""
echo "=== Configuring Redis ==="

# Password
if sudo grep -q "^requirepass " "$REDIS_CONF"; then
    sudo sed -i "s|^requirepass .*|requirepass $REDIS_PASSWORD|" "$REDIS_CONF"
else
    sudo sed -i "s|^# requirepass .*|requirepass $REDIS_PASSWORD|" "$REDIS_CONF"
fi

# Bind to all interfaces (NSG restricts access at the network level)
sudo sed -i "s|^bind 127\.0\.0\.1.*|bind 0.0.0.0|" "$REDIS_CONF"

# Memory limit
if sudo grep -q "^maxmemory " "$REDIS_CONF"; then
    sudo sed -i "s|^maxmemory .*|maxmemory $MAXMEMORY|" "$REDIS_CONF"
else
    sudo sed -i "s|^# maxmemory .*|maxmemory $MAXMEMORY|" "$REDIS_CONF"
fi

# Eviction policy
if sudo grep -q "^maxmemory-policy " "$REDIS_CONF"; then
    sudo sed -i "s|^maxmemory-policy .*|maxmemory-policy allkeys-lru|" "$REDIS_CONF"
else
    sudo sed -i "s|^# maxmemory-policy .*|maxmemory-policy allkeys-lru|" "$REDIS_CONF"
fi

# Disable persistence (rate-limit counters don't need to survive reboots)
sudo sed -i "s|^save 900|# save 900|" "$REDIS_CONF"
sudo sed -i "s|^save 300|# save 300|" "$REDIS_CONF"
sudo sed -i "s|^save 60|# save 60|" "$REDIS_CONF"

echo ""
echo "=== Configuring firewall ==="
if sudo ufw status | grep -q "Status: active"; then
    sudo ufw allow 6379/tcp comment "Redis"
    echo "ufw rule added for port 6379"
else
    echo "ufw is inactive - relying on Azure NSG for network access control"
fi

echo ""
echo "=== Starting Redis ==="
sudo systemctl restart redis-server
sudo systemctl enable redis-server

echo ""
echo "=== Verifying ==="
sleep 1
if redis-cli -a "$REDIS_PASSWORD" --no-auth-warning ping | grep -q PONG; then
    echo "Redis is running and responding"
    echo ""
    echo "Connection details:"
    echo "  Host: $(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
    echo "  Port: 6379"
else
    echo "ERROR: Redis did not respond to PING"
    sudo systemctl status redis-server
    exit 1
fi
