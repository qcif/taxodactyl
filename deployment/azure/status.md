# Azure Batch Integration Status

**Last Updated:** 2025-12-29
**Status:** ✅ **WORKING** - Basic Nextflow execution with reference data staging complete

---

## Current State

### What's Working ✅

1. **Azure Batch Pool Configuration**
   - Pool `taxodactyl` configured with Standard_L8as_v3 VMs (8 cores, 64GB RAM, 1.8TB NVMe)
   - Container-enabled Ubuntu 20.04 nodes
   - Configuration: [pool-setup.json.template](pool-setup.json.template)

2. **Start Task - Reference Data Staging**
   - NVMe detection and formatting (1.8TB ext4 filesystem)
   - azcopy installation from Microsoft CDN
   - Reference data download: 225GB in ~2.3 minutes (1.6 GB/s)
   - Data staged to `/mnt/nvme/refdata/core_nt` on host
   - Implementation: [setup.sh.template](setup.sh.template)

3. **Container Integration**
   - NVMe mounted into Docker containers at `/mnt/nvme/refdata` (read-only)
   - Container options configured in [conf/azure.config:26](../../conf/azure.config#L26)
   - Reference data accessible to all workflow processes

4. **Nextflow Execution**
   - Basic workflow tested successfully: [hello-world.nf](hello-world.nf)
   - All processes execute correctly (sayHello, createFile, checkRefData, mergeResults)
   - Reference data verified accessible inside containers
   - Results published to local `results/` directory

5. **Autoscaling**
   - Autoscaling works with `$ActiveTasks` variable
   - Nodes provision and start task runs automatically when tasks are submitted
   - Important limitations documented below

### Configuration Files

**Version-controlled (templates with placeholders):**
- [pool-setup.json.template](pool-setup.json.template) - Pool configuration
- [setup.sh.template](setup.sh.template) - Start task script
- [pool-test-start-task.json.template](pool-test-start-task.json.template) - Test pool config

**Local-only (gitignored, contain actual SAS tokens):**
- `pool-setup.json.ignore` - Pool config with setup script SAS token
- `setup.sh.ignore` - Start task with premium blob SAS token
- `pool-test-start-task.json.ignore` - Test config with test script SAS token

**Nextflow configuration:**
- [conf/azure.config](../../conf/azure.config) - Azure Batch executor settings
- [conf/profiles.config:21](../../conf/profiles.config#L21) - Azure profile definition

### Key Configuration Details

**Reference Data Path:**
- Host: `/mnt/nvme/refdata/core_nt/` (429 files, 225GB)
- Container: `/mnt/nvme/refdata/core_nt/` (read-only mount)
- Nextflow param: `params.refdata_path = "/mnt/nvme/refdata/core_nt"` (see [hello-world.nf:13](hello-world.nf#L13))

**Temp Directory:**
- Overridden to `/tmp/taxodactyl_tmp` for container compatibility
- See [conf/azure.config:12](../../conf/azure.config#L12)

**Container Registry:**
- Default registry: `quay.io` (set in [conf/profiles.config:128](../../conf/profiles.config#L128))
- Azure profile overrides to use `docker.io/library/ubuntu:20.04`

---

## Known Issues and Limitations

### 1. Autoscaling Limitations ⚠️

**Issue:** `$ActiveTasks` only detects RUNNING tasks, not queued tasks
- `$PendingTasks` always returns 0 for Nextflow-submitted tasks
- Tasks only appear in `$ActiveTasks` after they start running
- Creates chicken-and-egg problem: tasks need nodes to run, but autoscaling only sees them after running

**Autoscale Evaluation Interval:**
- Minimum: 5 minutes (Azure Batch limitation)
- Tasks can wait up to 5 minutes before nodes are provisioned

**Current Formula:**
```groovy
initialNodes=0;
maxNodes=1;
demand = avg($ActiveTasks.GetSample(TimeInterval_Minute * 1));
$TargetDedicatedNodes = min(max(demand, initialNodes), maxNodes);
```

**Workarounds:**
- Use fixed pool size for predictable workloads
- Accept 5-10 minute startup delay for on-demand scaling

### 2. Pool State Management

**Current state:** Pool resized to 0 nodes (autoscaling disabled)

**To scale up manually:**
```bash
az batch pool resize --pool-id taxodactyl --target-dedicated-nodes 1
```

**To re-enable autoscaling:**
```bash
az batch pool autoscale enable \
  --pool-id taxodactyl \
  --auto-scale-formula 'initialNodes=0; maxNodes=1; demand = avg($ActiveTasks.GetSample(TimeInterval_Minute * 1)); $TargetDedicatedNodes = min(max(demand, initialNodes), maxNodes);' \
  --auto-scale-evaluation-interval PT5M
```

### 3. SAS Token Management

**Security pattern established:**
- `*.ignore` files: contain actual SAS tokens (gitignored)
- `*.template` files: contain placeholders (version controlled)
- Pattern in [.gitignore:1](../../deployment/azure/.gitignore#L1)

**Active SAS tokens** (all expire 2026-12-29):
- Setup script SAS token (in `pool-setup.json.ignore`)
- Premium blob container SAS token (in `setup.sh.ignore`)
- Test script SAS token (in `pool-test-start-task.json.ignore`)

---

## Environment Setup

### Required Environment Variables

Stored in `.env.azure` (gitignored):
```bash
AZURE_BATCH_ACCOUNT_NAME=daffbatch
AZURE_BATCH_ACCESS_KEY=<primary_key>
AZURE_BATCH_ENDPOINT=https://daffbatch.australiaeast.batch.azure.com
AZURE_STORAGE_ACCOUNT_KEY=<standard_storage_key>
NXF_AZURE_REFERENCE_KEY=<premium_storage_key>
```

**Load before running commands:**
```bash
set -a && source .env.azure && set +a
```

### Azure Resources

**Batch Account:**
- Name: `daffbatch`
- Location: `australiaeast`
- Endpoint: `https://daffbatch.australiaeast.batch.azure.com`

**Storage Accounts:**
- `daffstandard` (standard tier) - for work directory, scripts
- `daffpremium` (premium tier) - for reference data

**Blob Containers:**
- `workdata` (standard) - Nextflow work directory
- `scripts` (standard) - start task scripts
- `refdata` (premium) - reference data (225GB)

---

## Running Workflows

### Test Workflow (Hello World)

```bash
# Load environment
set -a && source .env.azure && set +a

# Run test workflow
nextflow run deployment/azure/hello-world.nf -profile azure
```

**Expected duration:**
- With warm node: ~50 seconds
- With cold start (autoscaling): ~10-15 minutes (includes node provisioning + data staging)

**Output location:** `results/`

**Verification:**
- Check `results/refdata_check.txt` - should show "SUCCESS: Directory exists"
- Should list 429 files in `/mnt/nvme/refdata/core_nt`

---

## Next Steps

### 1. Create Bash Helper Functions

**Goal:** Make Azure Batch commands reproducible and easier to use

**Proposed helpers:**
- Pool management (create, delete, resize, scale)
- Node inspection (list, ssh, get logs)
- Job management (list, monitor, cancel)
- Storage operations (upload scripts, download logs)
- SAS token generation and rotation

**Implementation location:** `deployment/azure/batch-helpers.sh` (to be created)

### 2. Run Real Workflow on Batch

**After bash helpers are in place:**
- Test with actual production workflow
- Validate BLAST execution with reference data
- Monitor performance and costs
- Tune resource allocations (CPU, memory, time limits)

### 3. Documentation Updates

**Files to update:**
- [docs/azure-setup.md](../../docs/azure-setup.md) - Add bash helper usage
- Document cost monitoring and optimization strategies
- Add troubleshooting guide for common issues

---

## Testing Checklist

To verify the setup is working:

- [ ] Pool creates successfully
- [ ] Start task completes (node state: `idle`, start task: `completed`)
- [ ] Reference data staged to `/mnt/nvme/refdata/core_nt` (225GB, 429 files)
- [ ] Test workflow runs successfully
- [ ] Containers can access reference data at `/mnt/nvme/refdata/core_nt`
- [ ] Results published correctly
- [ ] Pool scales down to 0 nodes when idle (if autoscaling enabled)

---

## Important Files Reference

### Configuration Files
- [pool-setup.json.template](pool-setup.json.template) - Pool configuration template
- [setup.sh.template](setup.sh.template) - Start task script template
- [conf/azure.config](../../conf/azure.config) - Nextflow Azure Batch settings
- [conf/profiles.config](../../conf/profiles.config) - Profile definitions

### Test Files
- [hello-world.nf](hello-world.nf) - Test workflow
- [start-task-test.sh](start-task-test.sh) - Minimal start task test

### Documentation
- [docs/azure-setup.md](../../docs/azure-setup.md) - Comprehensive setup guide
- [.gitignore](.gitignore) - Security patterns for SAS tokens

---

## Performance Metrics

**Reference Data Staging:**
- Size: 225GB (429 files)
- Time: 2.3 minutes
- Throughput: 1.6 GB/second
- Source: Premium blob storage → NVMe SSD
- Tool: azcopy v10.31.0

**VM Specifications (Standard_L8as_v3):**
- CPU: 8 cores
- RAM: 64GB
- NVMe: 1.8TB (formatted as ext4)
- Cost: ~$0.68/hour (on-demand, australiaeast)

---

## Troubleshooting

### Start Task Fails
1. Check start task logs:
   ```bash
   NODE_ID=$(az batch node list --pool-id taxodactyl --query "[0].id" -o tsv)
   az batch node file download --pool-id taxodactyl --node-id $NODE_ID \
     --file-path startup/stderr.txt --destination /tmp/startup-stderr.txt
   cat /tmp/startup-stderr.txt
   ```

### Reference Data Not Accessible in Containers
1. Verify NVMe mount on host (via start task logs)
2. Check container volume mount in [conf/azure.config:26](../../conf/azure.config#L26)
3. Ensure path matches in workflow: [hello-world.nf:13](hello-world.nf#L13)

### Tasks Fail with "Permission Denied"
- Check `beforeScript` override in [conf/azure.config:22](../../conf/azure.config#L22)
- Ensure temp directory is container-writable (not /home/cameron/...)

### SAS Token Expired
- Regenerate tokens (all currently expire 2026-12-29)
- Update `*.ignore` files with new tokens
- Re-upload scripts to blob storage if setup.sh token changed