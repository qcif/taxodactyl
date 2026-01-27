# Known issues with Azure deployment

> Search for "! CAM" throughout the project to see issues that I've tagged in the code

1. Not all required files are captured as process outputs, causing REPORT to fail

1. It seems that only the first query is being passed to EXTRACT_CANDIDATES onwards - all other queries have all_hits.fasta in their output dir, nothing else. From EXTRACT_CANDIDATES onwards (where parallel processing begins) I see only query 1 being run. Perhaps this is an issue with `ch_hits`?

1. When a task fails, I haven't figured out a reliable way to archive the filesystem workdir to Azure blob for debugging. This is essential for reproducing and debugging errors. An `afterScript` is capable of uploading the archive with azcopy, but I couldn't figure out a way to tell if the task failed. This is critical because we can't do this for every task! Or perhaps there is a better way of doing this.

1. SAS tokens are used for authentication in several places, which will expire around December 2026. Need to set up a renewal/rotation strategy for these.

1. Need to set up automated updates for reference DBs.
