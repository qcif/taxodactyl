# Troubleshooting Azure Batch

This guide covers common issues and debugging techniques for Azure Batch integration.

## Table of Contents

- [Start Task Issues](#start-task-issues)
- [Reference Data Issues](#reference-data-issues)
- [Task Execution Issues](#task-execution-issues)
- [Authentication Issues](#authentication-issues)
- [Autoscaling Issues](#autoscaling-issues)
- [General Debugging Techniques](#general-debugging-techniques)

## Start Task Issues

### Start Task Fails

**Symptoms**: Node state is `starttaskfailed` or start task exit code is non-zero.

**Diagnosis**:

```bash
# Check start task status
NODE_ID=$(az batch node list --pool-id taxodactyl --query "[0].id" -o tsv)
az batch node list \
  --pool-id taxodactyl \
  --query "[].{id: id, state: state, startTaskState: startTaskInfo.state, startTaskResult: startTaskInfo.result, exitCode: startTaskInfo.exitCode}" \
  -o table

# Download and view start task logs
az batch node file download \
  --pool-id taxodactyl \
  --node-id $NODE_ID \
  --file-path startup/stderr.txt \
  --destination /tmp/startup-stderr.txt

cat /tmp/startup-stderr.txt
```

**Common Causes**:

1. **NVMe device not found**:
   - Check VM SKU has NVMe storage (L-series)
   - Verify device path in script matches actual device (`/dev/nvme0n1`)

2. **SAS token expired**:
   - Regenerate SAS tokens
   - Update `*.ignore` files with new tokens
   - Re-upload scripts if needed

3. **Permission errors**:
   - Ensure `elevationLevel: "admin"` in start task config
   - Check script has execute permissions

4. **azcopy installation failed**:
   - Check network connectivity to Microsoft CDN
   - Try alternative installation method (apt-based)

### Start Task Logs Not Available

**Symptoms**: Cannot download start task logs.

**Solution**:

```bash
# List all files in startup directory
az batch node file list \
  --pool-id taxodactyl \
  --node-id $NODE_ID \
  --path startup

# Try downloading stdout instead
az batch node file download \
  --pool-id taxodactyl \
  --node-id $NODE_ID \
  --file-path startup/stdout.txt \
  --destination /tmp/startup-stdout.txt
```

## Reference Data Issues

### Reference Data Not Accessible in Containers

**Symptoms**: Workflow fails with "directory not found" or "no such file" errors.

**Diagnosis**:

1. **Verify NVMe mount on host** (via start task logs):
   ```bash
   cat /tmp/startup-stderr.txt | grep -A 10 "mount"
   ```

2. **Check container volume mount** in [conf/azure.config:26](../../conf/azure.config#L26):
   ```groovy
   containerOptions = '-v /mnt/nvme/refdata:/mnt/nvme/refdata:ro'
   ```

3. **Ensure path matches in workflow**:
   ```groovy
   params.refdata_path = "/mnt/nvme/refdata/core_nt"
   ```

**Solutions**:

- Ensure all three paths are consistent
- Verify reference data was staged (check start task logs)
- Confirm container options are applied to processes

### Reference Data Download Fails

**Symptoms**: Start task fails during azcopy download.

**Common Causes**:

1. **Incorrect blob URL**:
   - Verify URL points to actual container/directory
   - Check for typos in container name or path

2. **SAS token issues**:
   - Ensure token has read (`r`) permissions
   - Check token has not expired
   - Verify token is properly URL-encoded

3. **Network issues**:
   - Check Azure service health
   - Verify network security group rules allow outbound HTTPS

**Solutions**:

```bash
# Test azcopy manually from a working machine
azcopy copy \
  "https://daffpremium.blob.core.windows.net/refdata/core_nt?<SAS_TOKEN>" \
  "./test_download" \
  --recursive \
  --log-level DEBUG

# Check blob exists
az storage blob list \
  --account-name daffpremium \
  --container-name refdata \
  --prefix core_nt/
```

## Task Execution Issues

### Tasks Fail with "Permission Denied"

**Symptoms**: Nextflow tasks fail with permission errors when writing to temp directory.

**Solution**:

Check `beforeScript` override in [conf/azure.config:22](../../conf/azure.config#L22):

```groovy
beforeScript = 'export TMPDIR=/tmp/taxodactyl_tmp && mkdir -p $TMPDIR'
```

Ensure temp directory is container-writable (not `/home/cameron/...`).

### Tasks Not Starting

**Symptoms**: Tasks remain in queue indefinitely.

**Diagnosis**:

```bash
# Check pool state and available slots
az batch pool show \
  --pool-id taxodactyl \
  --query "{
    state: state,
    dedicatedNodes: currentDedicatedNodes,
    runningTasks: runningTasksCount,
    maxTasksPerNode: taskSlotsPerNode
  }"

# List tasks
az batch task list \
  --job-id <job-id> \
  --query "[].{id: id, state: state, exitCode: executionInfo.exitCode}"
```

**Common Causes**:

1. **No available nodes**: Check autoscaling configuration
2. **All task slots full**: Increase nodes or wait for tasks to complete
3. **Start task failed**: Fix start task issues first

## Authentication Issues

### SAS Token Expired

**Symptoms**: Start task or data transfer fails with authorization errors.

**Solution**:

```bash
# Regenerate tokens (all currently expire 2026-12-29)
# For start task script
az storage blob generate-sas \
  --account-name daffstandard \
  --container-name scripts \
  --name setup.sh \
  --permissions r \
  --expiry $(date -u -d "+1 year" '+%Y-%m-%dT%H:%MZ') \
  --https-only \
  --output tsv

# For reference data
az storage container generate-sas \
  --account-name daffpremium \
  --name refdata \
  --permissions r \
  --expiry $(date -u -d "+1 year" '+%Y-%m-%dT%H:%MZ') \
  --https-only \
  --output tsv

# Update *.ignore files with new tokens
# Re-upload scripts to blob storage if setup.sh token changed
```

### Environment Variables Not Set

**Symptoms**: `az batch` commands fail with authentication errors.

**Solution**:

```bash
# Load environment from .env.azure
set -a && source .env.azure && set +a

# Verify variables are set
echo $AZURE_BATCH_ACCOUNT_NAME
echo $AZURE_BATCH_ENDPOINT
```

## Autoscaling Issues

### Pool Not Scaling Up

**Symptoms**: Tasks queued but no nodes provisioning.

**Known Limitation**: `$ActiveTasks` only detects RUNNING tasks, not queued tasks.

**Diagnosis**:

```bash
# Check autoscale formula evaluation
az batch pool autoscale evaluate \
  --pool-id taxodactyl \
  --auto-scale-formula '
    initialNodes=0;
    maxNodes=1;
    demand = avg($ActiveTasks.GetSample(TimeInterval_Minute * 1));
    $TargetDedicatedNodes = min(max(demand, initialNodes), maxNodes);'
```

**Workarounds**:

1. **Use fixed pool size** for predictable workloads:
   ```bash
   az batch pool resize --pool-id taxodactyl --target-dedicated-nodes 1
   ```

2. **Accept 5-10 minute startup delay** for on-demand scaling

3. **Manually scale up** before submitting large workloads

### Autoscaling Disabled

**Symptoms**: Autoscaling formula not being evaluated.

**Solution**:

```bash
# Re-enable autoscaling
az batch pool autoscale enable \
  --pool-id taxodactyl \
  --auto-scale-formula '
    initialNodes=0;
    maxNodes=1;
    demand = avg($ActiveTasks.GetSample(TimeInterval_Minute * 1));
    $TargetDedicatedNodes = min(max(demand, initialNodes), maxNodes);' \
  --auto-scale-evaluation-interval PT5M
```

## General Debugging Techniques

### Enable Verbose Logging

**In start task script**:
```bash
set -x  # Enable verbose logging
```

**In Nextflow**:
```bash
nextflow run workflow.nf -profile azure -with-trace -with-timeline -with-dag
```

### SSH to Compute Node

**Enable SSH** (must be configured at pool creation):

```json
{
  "networkConfiguration": {
    "endpointConfiguration": {
      "inboundNATPools": [
        {
          "name": "SSH",
          "protocol": "tcp",
          "backendPort": 22,
          "frontendPortRangeStart": 50000,
          "frontendPortRangeEnd": 50100
        }
      ]
    }
  }
}
```

**Connect to node**:

```bash
# Get node connection info
NODE_ID=$(az batch node list --pool-id taxodactyl --query "[0].id" -o tsv)
az batch node user create \
  --pool-id taxodactyl \
  --node-id $NODE_ID \
  --name debuguser \
  --password <secure-password>

az batch node remote-login-settings show \
  --pool-id taxodactyl \
  --node-id $NODE_ID

# SSH using the provided IP and port
ssh debuguser@<ip-address> -p <port>
```

### View All Node Files

```bash
# List all files on a node
az batch node file list \
  --pool-id taxodactyl \
  --node-id $NODE_ID \
  --recursive

# Download specific file
az batch node file download \
  --pool-id taxodactyl \
  --node-id $NODE_ID \
  --file-path <path> \
  --destination <local-path>
```

### Monitor Job Progress

```bash
# List all jobs
az batch job list --query "[].{id: id, state: state}"

# Show job details
az batch job show --job-id <job-id>

# List tasks in a job
az batch task list \
  --job-id <job-id> \
  --query "[].{id: id, state: state, exitCode: executionInfo.exitCode, startTime: executionInfo.startTime}"
```

## Getting Help

If you're still experiencing issues:

1. Check [deployment/azure/status.md](../../deployment/azure/status.md) for known issues
2. Review Azure Batch service health: https://status.azure.com/
3. Check Nextflow documentation: https://www.nextflow.io/docs/latest/azure.html
4. Review start task logs with verbose logging enabled
5. Create an issue with detailed logs and error messages

## Useful Commands Reference

```bash
# Load environment
set -a && source .env.azure && set +a

# Check pool status
az batch pool show --pool-id taxodactyl

# List nodes
az batch node list --pool-id taxodactyl

# Check node state
az batch node list \
  --pool-id taxodactyl \
  --query "[].{id: id, state: state, startTask: startTaskInfo.state}"

# Scale pool manually
az batch pool resize --pool-id taxodactyl --target-dedicated-nodes 1

# Delete pool (emergency)
az batch pool delete --pool-id taxodactyl
```
