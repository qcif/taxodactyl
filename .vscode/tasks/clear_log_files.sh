# Delete log files/directories in the output directory

find output -type f -name '*.log' -delete
find output -type d -name 'errors' -exec rm -rf {} \; || true
