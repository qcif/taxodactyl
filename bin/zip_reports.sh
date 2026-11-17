#!/usr/bin/bash

# Zip all workflow reports into a single file for easy download
#
# Pass --coverage_taxa (with or without the coverage CSV path) when the
# workflow was run in database coverage mode, where there is nothing to zip.

COVERAGE_MODE=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dir) DIR="$2"; shift ;;
        --coverage_taxa)
            COVERAGE_MODE=true
            # Optional value: the coverage CSV path
            if [[ -n "${2:-}" && "$2" != --* ]]; then shift; fi
            ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [[ "$COVERAGE_MODE" == true ]]; then
    echo "Running in database coverage mode - samples are aggregated into a single run-level report. Nothing to zip."
    exit 0
fi

if [[ -z "$DIR" ]]; then
    echo "Usage: $0 --dir <directory> [--coverage_taxa]"
    exit 1
fi


cd "$DIR"
mkdir reports
cp query_*/report*.html reports
zip -r reports.zip reports/ > /dev/null

echo "All workflow reports have been zipped"
echo 'You can download all workflow reports by clicking the reports.zip file under "Results" tab.'
