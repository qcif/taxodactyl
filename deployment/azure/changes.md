# Azure Batch Integration Changes

This document tracks all changes made to the Taxodactyl workflow to support Azure Batch execution.

## Critical Bug Fixes

### 1. Fixed invalid `Channel.fromPath()` parameter
**File**: `workflows/taxodactyl.nf:93`

**Issue**: The workflow was calling `Channel.fromPath(blastdb_uri_glob, enableRemote=true)` with an invalid parameter `enableRemote=true` that doesn't exist in Nextflow's API.

**Error**:
```
Missing process or function Channel.fromPath([/mnt/data/blast/*, true])
```

**Fix**: Removed the `enableRemote=true` parameter. `Channel.fromPath()` already supports both local and remote paths (including Azure Blob Storage) without needing any special flag.

```groovy
// Before
ch_refdata_blastdb = Channel.fromPath(blastdb_uri_glob, enableRemote=true)

// After
ch_refdata_blastdb = Channel.fromPath(blastdb_uri_glob)
```

### 2. Updated nf-azure plugin for Nextflow 25.10.2 compatibility
**File**: `conf/misc.config:40`

**Issue**: The nf-azure plugin version 1.16.0 was incompatible with Nextflow 25.10.2, causing a method signature mismatch error.

**Error**:
```
java.lang.NoSuchMethodError: 'nextflow.processor.TaskPollingMonitor
nextflow.processor.TaskPollingMonitor.create(nextflow.Session, java.lang.String, int, nextflow.util.Duration)'
```

**Fix**: Changed from pinned version to using the latest compatible version:

```groovy
// Before
id 'nf-azure@1.16.0'

// After
id 'nf-azure'  // Use latest compatible version
```

**Result**: Nextflow automatically selects the latest version compatible with the installed Nextflow version (25.10.2).

### 3. Added default container for Azure Batch processes
**File**: `conf/azure.config:25`

**Issue**: Azure Batch executor requires all processes to have a container specified. Many lightweight processes (like `PREPARE_INPUTS`) don't have explicit containers because they were designed for local execution.

**Error**:
```
No container image specified for process QCIF_TAXODACTYL:TAXODACTYL:PREPARE_INPUTS (metadata.csv)
-- Either specify the container to use in the process definition or with 'process.container' value in your config
```

**Fix**: Added a default Ubuntu container for processes without explicit containers:

```groovy
process {
    executor = 'azurebatch'
    queue = 'taxodactyl'

    // Default container for processes without container specified
    container = 'ubuntu:24.04'

    // ... rest of config
}
```

**Result**: All processes now have a container and can run on Azure Batch.

### 4. Created Azure Batch execution script
**File**: `deployment/azure/run-taxodactyl.sh`

**Purpose**: Provides a convenient wrapper for running the Taxodactyl workflow on Azure Batch with proper configuration.

**Features**:
- Automatically loads Azure credentials from `.env.azure`
- Uses correct NVMe-staged paths for reference data:
  - BLAST DB: `/mnt/nvme/refdata/blast/core_nt`
  - Tax DB: `/mnt/nvme/refdata/taxdump`
- Provides sensible defaults for test data
- Validates required environment variables
- Interactive confirmation before execution

**Usage**:
```bash
./deployment/azure/run-taxodactyl.sh \
    --metadata /path/to/metadata.csv \
    --sequences /path/to/sequences.fasta \
    --outdir /path/to/output \
    -resume
```

## Additional Nextflow Changes

### 5. Added Azure profile configuration
**File**: `conf/profiles.config`

**Change**: Added `azure` profile that loads the Azure Batch configuration:

```groovy
azure {
    includeConfig 'azure.config'
}
```

**Usage**: Enable Azure Batch with `-profile azure` or `-profile singularity,azure`

### 6. Moved Singularity profile position
**File**: `conf/profiles.config`

**Change**: Moved the `singularity` profile definition to appear before other profiles (cosmetic change for better organization).

### 7. Updated BLAST module for Azure compatibility
**File**: `modules/blast/blastn/main.nf`

**Changes**:
1. **Removed hardcoded `containerOptions`**: The old `--bind ${file(params.blastdb).parent}` was specific to local filesystem mounting and incompatible with Azure Batch.

2. **Changed to explicit directory input**: Instead of using `params.blastdb` directly, the module now receives the BLAST database directory as an input channel:

```groovy
// Before
process BLAST_BLASTN {
    containerOptions "--bind ${file(params.blastdb).parent}"

    input:
    path(fasta)
    val ready

    script:
    """
    blastn -db ${file(params.blastdb)} ...
    """
}

// After
process BLAST_BLASTN {
    input:
    path(fasta)
    tuple path(core_nt_dir), val(blastdb_name)
    val ready

    script:
    """
    blastn -db ${core_nt_dir}/${blastdb_name} ...
    """
}
```

**Rationale**:
- The Azure Batch configuration now handles container volume mounting via `containerOptions = '-v /mnt/nvme/refdata:/mnt/nvme/refdata:ro'` in `conf/azure.config`
- This approach is more flexible and allows the same module to work with both local and Azure Batch executors
- The workflow constructs the BLAST database path from the parameter and passes it as a channel input

### 8. Updated workflow to pass BLAST DB as channel
**File**: `workflows/taxodactyl.nf:90-98`

**Change**: Modified the BLAST invocation to construct and pass the database directory as a channel:

```groovy
// Parse blastdb parameter to extract directory and database name
def blastdb_name = params.blastdb.tokenize('/').last()
def blastdb_uri = params.blastdb - "/${blastdb_name}"
def blastdb_uri_glob = "${blastdb_uri}/*"

// Create channel from database directory
ch_refdata_blastdb = Channel.fromPath(blastdb_uri_glob)
blastdb_dir_ch = ch_refdata_blastdb.collect()

// Pass as tuple (directory, database_name)
BLAST_BLASTN (
    ch_sequences,
    blastdb_dir_ch.map { it -> [it, blastdb_name] },
    VALIDATE_INPUT.out
)
```

**Rationale**:
- Allows Nextflow to stage the BLAST database files appropriately for different executors
- Works seamlessly with both local filesystem and Azure Blob Storage paths
- Maintains separation of concerns: the workflow manages data location, the process manages execution

## Documentation Changes

The following documentation files were created/updated:
- `docs/azure/README.md`
- `docs/azure/01-initial-setup.md`
- `docs/azure/02-pool-management.md`
- `docs/azure/03-reference-data.md`
- `docs/azure/04-start-tasks.md`
- `docs/azure/05-troubleshooting.md`

These provide comprehensive guides for Azure Batch setup, configuration, and troubleshooting.

## Schema Changes

**File**: `nextflow_schema.json`

Minor updates to parameter descriptions and validation rules to support Azure Batch execution.

## Bind mounts

Were hard-coded as singularity mounts (`--bind <path>`). These were changed to hard-coded docker volume mount params `-v` but should be refactored so that the process.conf sets the bind mount flag and azure.conf can override it.

## Summary

All changes were made to:
1. Fix compatibility issues with Nextflow 25.10.2 and Azure Batch
2. Enable flexible execution across local and cloud environments
3. Implement cost-efficient single-node Azure Batch execution strategy
4. Maintain backward compatibility with existing local/Singularity execution

The workflow can now run seamlessly on Azure Batch while preserving the ability to run locally with the same codebase.
