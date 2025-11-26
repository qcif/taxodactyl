#!/usr/bin/env bash

set -euo pipefail

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

NVME_MNT="/mnt/nvme"
REFDATA_DIR="$NVME_MNT/refdata"
BLOB_URL="https://daffpremium.blob.core.windows.net/refdata/data"

# -----------------------------------------------------------------------------
# FUNCTIONS
# -----------------------------------------------------------------------------

detect_nvme_device() {
    # Detect the NVMe disk by type "disk" and looking for "nvme"
    local dev
    dev=$(lsblk -ndo NAME,TYPE | awk '$2=="disk" {print $1}' | grep nvme | head -n 1)

    if [[ -z "$dev" ]]; then
        echo "ERROR: No NVMe disk detected." >&2
        exit 1
    fi

    echo "/dev/$dev"
}

mount_nvme() {
    local dev="$1"

    # Create mount point
    sudo mkdir -p "$NVME_MNT"

    # If not formatted, create ext4 filesystem
    if ! sudo blkid "$dev" >/dev/null 2>&1; then
        echo "Formatting NVMe device $dev..."
        sudo mkfs.ext4 -F "$dev"
    fi

    # Mount if not mounted
    if ! mount | grep -q "$NVME_MNT"; then
        echo "Mounting NVMe filesystem..."
        sudo mount "$dev" "$NVME_MNT"
        sudo chown -R "$USER:$USER" "$NVME_MNT"
    fi
}

stage_refdata() {
    # If refdata already exists → assume this is a warm node
    if [[ -d "$REFDATA_DIR" ]]; then
        echo "Refdata already staged at $REFDATA_DIR — skipping download."
        return
    fi

    echo "Staging reference data from blob..."
    mkdir -p "$REFDATA_DIR"

    # Note:
    # --check-md5 NoCheck = fastest
    # --cap-mbps 0 = unlimited throughput
    # azcopy automatically uses optimal parallelism
    azcopy copy \
        "${BLOB_URL}" \
        "${REFDATA_DIR}" \
        --recursive \
        --check-md5 NoCheck \
        --cap-mbps 0

    echo "Reference data staged successfully."
}

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

echo "===== START TASK: Begin staging refdata on NVMe ====="

NVME_DEV=$(detect_nvme_device)
echo "Detected NVMe device: $NVME_DEV"

mount_nvme "$NVME_DEV"

stage_refdata

echo "===== START TASK: Completed ====="
