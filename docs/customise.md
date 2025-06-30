To add or modify configuration for a Nextflow pipeline, you typically use a `nextflow.config` file in your working directory, or you can specify a custom config file with the `-c` option when running the pipeline.

Nextflow automatically loads `nextflow.config` from the current directory, the pipeline directory, and any included config files. If you want to use a different configuration, provide a custom config file with `-c /path/to/custom.config` when running Nextflow.

Any settings in your local or custom config file will override the defaults set in the pipeline. In these config files, you can set parameters, profiles, resource requirements, or error strategies.

The pipeline’s default configuration files are located in the `conf` folder. For example, [conf/process.config](../conf/process.config) contains the default resource settings (such as CPUs, memory, and time) and container images for each process in the pipeline.

For more details, see the [technical documentation for this pipeline](detailled_tech.md) and the [Nextflow configuration documentation](https://www.nextflow.io/docs/latest/config.html).

The following sections provide practical examples of how to customise your pipeline configuration:

### Modifying the Singularity cache directory

You may want to change the default cache directory where container images are stored. This can be useful if you have limited space in your home directory or want to use a shared cache location.

You can set the cache directory directly in your Nextflow config file like this:

```groovy
singularity {
    cacheDir = '/path/to/images'
}
```

### Customising resources for a process

To change the memory or CPU allocation for a specific process, add or modify a `withName` block in your config file. For example, to set the `BLAST_BLASTN` process to use 8 CPUs and 16GB of memory, set the following:

```
process {
    withName: BLAST_BLASTN {
        cpus = 8
        memory = '16GB'
    }
}
```

### Error strategy

The error strategy for the workflow is set to `ignore`. It means that even if a process encounters an error, Nextflow will continue executing subsequent processes rather than terminating the workflow. This is to avoid interrupting the entire workflow with multiple queries when only one of them fails. To overwrite, add or modify the following block in a config file to specify the error strategy 
```
process {
    errorStrategy = 'ignore'
}
```
Replace `ignore` with the desired error handling strategy, such as `terminate`, `retry`, or `finish`, depending on the desired behavior. See [Nextflow documentation](https://www.nextflow.io/docs/latest/reference/process.html#process-error-strategy) for details. 

### Parameters

For reproducibility and convenience, especially when using the same values repeatedly, you can set parameters in your `nextflow.config` or a custom config file. This avoids having to type them every time you run the pipeline and can be useful for parametres such as the path to the BLAST database, analyst/facility name, or your NCBI API key or user name. Example:

 ```groovy
params {
    blastdb      = '/path/to/blast/db/core_nt'
    ncbi_user_email = 'your.email@example.com'
    ncbi_api_key    = 'YOUR_NCBI_API_KEY'
    analyst_name    = 'Your Name'
    facility_name   = 'Your Facility'
}
  ```

Any parameter set in your config file will override the pipeline defaults (see `conf/params.config` for all available parameters and their default values).  
You can combine both methods: parameters set on the command line will override those in the config file.

### Example

Example Nextflow config file demonstrating customisation

```groovy
// Set a custom Singularity cache directory
singularity {
    cacheDir = '/path/to/images'
}

// Customise resources for a specific process
process {
    withName: BLAST_BLASTN {
        cpus = 8
        memory = '16GB'
    }
    // Set the default error strategy for all processes
    errorStrategy = 'terminate'
}

// Set pipeline parameters
params {
    blastdb      = '/path/to/blast/db/core_nt'
    ncbi_user_email = 'your.email@example.com'
    ncbi_api_key    = 'YOUR_NCBI_API_KEY'
    analyst_name    = 'Your Name'
    facility_name   = 'Your Facility'
}
```