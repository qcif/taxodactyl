# Azure Batch Setup Documentation

This directory contains comprehensive documentation for running Taxodactyl workflows on Azure Batch.

## Documentation Index

1. **[Initial Setup](01-initial-setup.md)** - Creating Azure resources (subscription, storage accounts, batch account, quotas)
2. **[Pool Management](02-pool-management.md)** - Creating and managing batch pools, autoscaling, and persistent nodes
3. **[Reference Data](03-reference-data.md)** - Uploading and staging reference data with NVMe storage
4. **[Start Tasks](04-start-tasks.md)** - Configuring start tasks for node initialization and reference data staging
5. **[Troubleshooting](05-troubleshooting.md)** - Common issues and debugging techniques

## Helper Scripts

For convenient command-line management of Azure Batch resources, use the bash helper functions at [deployment/azure/batch-helpers.sh](../../deployment/azure/batch-helpers.sh).

### Quick Start with Helper Functions

```bash
# Load the helper functions (automatically loads .env.azure if present)
source deployment/azure/batch-helpers.sh

# View all available commands
azure_help

# Common operations
azure_pool_list                    # List all pools
azure_pool_show                    # Show pool details
azure_pool_resize 1                # Scale up to 1 node
azure_node_logs                    # Download start task logs
azure_jobs_list                    # List recent jobs
```

### Available Helper Functions

**Pool Management:**
- `azure_pool_create <json> [autoscale] [--yes]` - Create pool from JSON config
- `azure_pool_delete [pool_id] [--yes]` - Delete pool
- `azure_pool_resize <0|1> [pool_id] [--yes]` - Resize pool
- `azure_pool_update <json> [pool_id] [--yes]` - Update pool configuration
- `azure_pool_list` / `azure_pool_show` - View pool information

**Node Management:**
- `azure_nodes_list [pool_id]` - List all nodes
- `azure_node_get_id [pool_id] [index]` - Get node ID
- `azure_node_logs [pool_id] [stderr|stdout] [output_dir]` - Download logs

**Job Management:**
- `azure_jobs_list` - List all jobs
- `azure_job_get_latest [pool_id]` - Get latest job ID
- `azure_job_logs [pool_id]` - Show tasks for latest job

**Storage Management:**
- `azure_storage_upload <src> <dest> [account] [container] [--yes]` - Upload files
- `azure_storage_download <blob> <dest> [account] [container]` - Download files
- `azure_storage_list [container] [account]` - List blobs

**SAS Token Management:**
- `azure_sas_generate <blob> [account] [container] [days]` - Generate SAS tokens

All destructive operations (create, delete, resize, update, upload) require confirmation unless `--yes` flag is provided for scripting.

## Quick Start

If you already have the Azure resources set up, see [Pool Management](02-pool-management.md) to create a pool and [deployment/azure/status.md](../../deployment/azure/status.md) for the current working configuration.

## Current Status

For the latest status of Azure Batch integration, see [deployment/azure/status.md](../../deployment/azure/status.md).
