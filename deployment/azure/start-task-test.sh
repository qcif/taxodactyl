#!/bin/bash
# Minimal start task test script
# This script verifies basic execution and logging capabilities

# Enable verbose logging
set -x

# Print basic environment info
echo "=== Start Task Test ==="
echo "Date: $(date)"
echo "User: $(whoami)"
echo "Working directory: $(pwd)"
echo "Hostname: $(hostname)"

# Check if running with elevated privileges
if [ -w /etc ]; then
    echo "Running with admin privileges: YES"
else
    echo "Running with admin privileges: NO"
fi

# List available storage
echo "=== Available Storage ==="
df -h

# Check for NVMe devices
echo "=== NVMe Devices ==="
ls -la /dev/nvme* 2>&1 || echo "No NVMe devices found"

# Create a test directory
TEST_DIR="/mnt/batch/tasks/startup/wd/test_output"
mkdir -p "$TEST_DIR"
echo "Test file created at $(date)" > "$TEST_DIR/test.txt"
echo "Created test file: $TEST_DIR/test.txt"

echo "=== Start Task Completed Successfully ==="
exit 0
