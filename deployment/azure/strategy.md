# Azure Batch Configuration Summary

This document summarizes the Azure Batch configuration for the Taxodactyl pipeline.

## Cost-Efficient Single-Node Strategy

All processes run on a single Azure Batch node to minimize reference data staging costs.

### Pool Configuration
- **Autoscaling**: 0-1 nodes (via `batch-helpers.sh`)
- **Node retention**: 15 minutes after tasks complete
- **VM size**: Standard_L8as_v3 (8 vCPU, 64GB RAM, 1.7TB NVMe)
- **Reference data**: Staged once per node to NVMe at startup (250GB)

### Process Resource Allocation

#### BLAST_BLASTN
- **Executor**: azurebatch
- **CPUs**: 8 (full node)
- **Memory**: 64 GB (full node)
- **maxForks**: 1 (one BLAST at a time)
- **Time limit**: 1 hour
- **Reference data**: Mounted from `/mnt/nvme/refdata`

#### MAFFT_ALIGN & FASTME
- **Executor**: azurebatch
- **CPUs**: 4 (half node)
- **Memory**: 32 GB (half node)
- **maxForks**: 2 (two tasks in parallel)
- **Time limit**: 1 hour
- **Reference data**: Mounted from `/mnt/nvme/refdata`

#### All Other Processes
- **Executor**: azurebatch
- **CPUs**: 1
- **Memory**: 2 GB
- **maxForks**: 16 (queue up on single node)
- **Time limit**: 30 minutes
- **Reference data**: Not needed

### How It Works

1. **Pipeline starts**: No nodes running (cost = $0)

2. **Tasks arrive**: Autoscaler spins up 1 node
   - Node runs start task: Downloads 250GB reference data to NVMe (~10-15 min)
   - Node is ready to accept tasks

3. **Task execution**:
   - BLAST runs one at a time (maxForks=1) using full node resources
   - MAFFT/FASTME can run 2 in parallel (maxForks=2) using half node each
   - Lightweight tasks queue up to 16 in parallel (maxForks=16)
   - All tasks share the same pre-staged reference data

4. **Pipeline completes**: Node stays warm for 15 minutes
   - If new pipeline starts within 15 min: No re-staging needed!
   - After 15 min idle: Node deallocates (cost = $0)

### Cost Benefits

- **Single node**: Reference data staged once, not per-task
- **NVMe storage**: Fast local staging, no repeated network transfers
- **Node retention**: Multiple pipeline runs can reuse warm node
- **Autoscaling**: Only pay for compute when tasks are running
- **Resource optimization**: Node fully utilized by different process types

### Work Directory

All processes use Azure Blob Storage for work directory: `az://workdata/work`
- Required for azurebatch executor
- Enables seamless file sharing between all processes
- Minimal overhead for small intermediate files