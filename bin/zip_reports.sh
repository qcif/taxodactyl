#!/usr/bin/bash

# Zip all workflow reports into a single file for easy download

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dir) DIR="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "$DIR" ]]; then
    echo "Usage: $0 --dir <directory>"
    exit 1
fi


cd "$DIR"
mkdir reports
find . -name report*.html -path *query_* -exec cp {} reports/ \; > /dev/null
zip -r reports.zip reports/ > /dev/null

echo "All workflow reports have been zipped"
echo 'You can download all workflow reports by clicking the reports.zip file under "Results" tab.'
