# Azure Batch Setup Documentation

This directory contains comprehensive documentation for running Taxodactyl workflows on Azure Batch.

## Quick start - running the workflow on Azure

This assumes that you have an Azure Batch pool set up and configured according
to the docs above.

1. Create a `.env.azure` file in the project root (see `.env.azure.sample`)
1. `deployment/azure/run-taxodactyl.sh --metadata my.csv --sequences seqs.fasta`

This will run Nextflow locally and send tasks to run on an Azure Batch node.
The pool can be configured with autoscale such that it defaults to zero nodes, and then spawns an ephemeral node when Nextflow submits a task to the pool.
The node is then "kept warm" for a period of time after workflow completion (typically 30 mins), and with subsequent jobs re-using the same node.
This results in a nice balance between cost and performance - it costs nothing until the workflow is run, and requires 5-8 minutes to launch the node and stage reference databases.

---

## Documentation Index

1. **[Initial Setup](01-initial-setup.md)** - Creating Azure resources (subscription, storage accounts, batch account, quotas)
2. **[Pool Management](02-pool-management.md)** - Creating and managing batch pools, autoscaling, and persistent nodes
3. **[Reference Data](03-reference-data.md)** - Uploading and staging reference data with NVMe storage
4. **[Start Tasks](04-start-tasks.md)** - Configuring start tasks for node initialization and reference data staging
5. **[Troubleshooting](05-troubleshooting.md)** - Common issues and debugging techniques
6. **[Maintenance](06-maintenance.md)** - Recurring maintenance tasks (SAS rotation, cache cleanup, key rotation)
7. **[Redis](07-redis.md)** - Always-on Redis VM for distributed rate-limiting across concurrent workflow instances

## Azure CLI

Azure CLI can be used to administer and configure Azure Batch resources. You can also use the web portal, but command-line is easier to document, share and reproduce.

For convenient command-line management of Azure Batch resources, use the bash helper functions at [deployment/azure/batch-helpers.sh](../../deployment/azure/batch-helpers.sh). Docs will describe full commands for interacting with Azure, but in most cases a helper function can be used instead.

### Helper Functions for Azure CLI

```bash
# Load the helper functions (automatically loads .env.azure if present)
source deployment/azure/batch-helpers.sh

# View all available commands
az_help

# Common operations
az_pool_list                    # List all pools
az_pool_show                    # Show pool details
az_pool_resize 1                # Scale up to 1 node
az_node_list                    # List all nodes in the default pool
az_node_logs                    # Download start task logs
az_jobs_list                    # List recent jobs
```

**Pool Management:**
- `az_pool_create <json> [autoscale] [--yes]` - Create pool from JSON config
- `az_pool_delete [pool_id] [--yes]` - Delete pool
- `az_pool_resize <0|1> [pool_id] [--yes]` - Resize pool
- `az_pool_update <json> [pool_id] [--yes]` - Update pool configuration
- `az_pool_list` / `az_pool_show` - View pool information

**Node Management:**
- `az_nodes_list [pool_id]` - List all nodes
- `az_node_get_id [pool_id] [index]` - Get node ID
- `az_node_logs [pool_id] [stderr|stdout] [output_dir]` - Download logs

**Job Management:**
- `az_jobs_list` - List all jobs
- `az_job_get_latest [pool_id]` - Get latest job ID
- `az_job_logs [pool_id]` - Show tasks for latest job

**Storage Management:**
- `az_storage_upload <src> <dest> [account] [container] [--yes]` - Upload files
- `az_storage_download <blob> <dest> [account] [container]` - Download files
- `az_storage_list [container] [account]` - List blobs

**SAS Token Management:**
- `az_sas_generate <blob> [account] [container] [days]` - Generate SAS tokens

**Redis VM Management:**
- `az_redis_vm_status` - Show VM power state and Redis reachability
- `az_redis_vm_start [--yes]` - Start a deallocated Redis VM
- `az_redis_vm_stop [--yes]` - Deallocate Redis VM (stops compute billing)
- `az_redis_vm_ssh` - Open SSH session to Redis VM

All destructive operations (create, delete, resize, update, upload) require confirmation unless `--yes` flag is provided for scripting.

## Set up a pool

If you already have the Azure resources set up, see [Pool Management](02-pool-management.md) to create a pool and [deployment/azure/status.md](../../deployment/azure/status.md) for the current working configuration.
