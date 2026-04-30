# Delete log files/directories in the output directory

find scripts/output -type f -name '*.log' -delete
rm -rf scripts/output/*/errors/
