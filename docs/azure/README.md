# Azure Batch Setup Documentation

This directory contains comprehensive documentation for running Taxodactyl workflows on Azure Batch.

## Documentation Index

1. **[Initial Setup](01-initial-setup.md)** - Creating Azure resources (subscription, storage accounts, batch account, quotas)
2. **[Pool Management](02-pool-management.md)** - Creating and managing batch pools, autoscaling, and persistent nodes
3. **[Reference Data](03-reference-data.md)** - Uploading and staging reference data with NVMe storage
4. **[Start Tasks](04-start-tasks.md)** - Configuring start tasks for node initialization and reference data staging
5. **[Troubleshooting](05-troubleshooting.md)** - Common issues and debugging techniques

## Helper Scripts

For convenient command-line management of Azure Batch resources, use the bash helper functions at [deployment/azure/batch-helpers.sh](../../deployment/azure/batch-helpers.sh). Docs will describe full commands for interacting with Azure, but in most cases a helper function can be used instead.

### Quick Start with Helper Functions

```bash
# Load the helper functions (automatically loads .env.azure if present)
source deployment/azure/batch-helpers.sh

# View all available commands
az_help

# Common operations
az_pool_list                    # List all pools
az_pool_show                    # Show pool details
az_pool_resize 1                # Scale up to 1 node
az_node_logs                    # Download start task logs
az_jobs_list                    # List recent jobs
```

### Available Helper Functions

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

All destructive operations (create, delete, resize, update, upload) require confirmation unless `--yes` flag is provided for scripting.

## Quick Start

If you already have the Azure resources set up, see [Pool Management](02-pool-management.md) to create a pool and [deployment/azure/status.md](../../deployment/azure/status.md) for the current working configuration.

## Current Status

For the latest status of Azure Batch integration, see [deployment/azure/status.md](../../deployment/azure/status.md).
