# Delete log files/directories in the output directory

find scripts/output -type f -name '*.log' -delete
find scripts/output -type d -name 'errors' -exec rm -rf {} \; || true
