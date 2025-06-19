The error strategy for the workflow is set to `ignore`. It means that even if a process encounters an error, Nextflow will continue executing subsequent processes rather than terminating the workflow. This is to avoid interrupting the entire workflow with multiple queries when only one of them fails. To overwrite, create a file named nextflow.config, if it does not already exist, in the execution folder. Add or modify the following block in nextflow.config to specify the error strategy 
```
process {
    errorStrategy = 'ignore'
}
```
Replace `ignore` with the desired error handling strategy, such as `terminate`, `retry`, or `finish`, depending on the desired behavior. See https://www.nextflow.io/docs/latest/reference/process.html#process-error-strategy for details. 