#!/usr/bin/env bash

# Run all integration tests from a terminal

if [[ ! -d "scripts/tests/integration" ]]; then
    echo "Integration tests directory not found. Please run from the project root."
    exit 1
fi

SCRIPT_NAME=test_integration.py

export PYTHONPATH="$PWD/scripts"
export TAXONKIT_DATA="$HOME/.taxonkit"
export LOGGING_DEBUG=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep)
            export KEEP_OUTPUTS=1
            shift
            ;;
        --continue)
            export SKIP_PASSED_TESTS=1
            shift
            ;;
        --bold)
            SCRIPT_NAME=test_integration_bold.py
            shift
            ;;
        --test_case)
            export RUN_TEST_CASE="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

python -m unittest discover -f -v \
    -s scripts/tests/integration \
    -p $SCRIPT_NAME
