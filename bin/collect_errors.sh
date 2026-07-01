#!/usr/bin/bash

set -euo pipefail

usage() {
  echo "Usage: $0 --dir <outdir>"
  echo "Expected errors at: <outdir>/errors"
}

DIR=""

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --dir)
      if [[ "${2:-}" == "" ]]; then
        echo "Missing value for --dir"
        usage
        exit 1
      fi
      DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown parameter passed: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$DIR" ]]; then
  usage
  exit 1
fi

source_errors_dir="${DIR%/}/errors"
errors_zip="${DIR%/}/errors.zip"

if [[ ! -d "$source_errors_dir" ]]; then
  echo "No errors occurred"
  echo "Directory $source_errors_dir not found"
  exit 0
fi

found_err=0

while IFS= read -r -d '' err_file; do
  found_err=1
  rel_path="${err_file#"$source_errors_dir"/}"

  echo
  echo "Error file: ${rel_path}"
  echo "Last 10 lines of stderr:"
  tail -n 10 "$err_file" || true
  echo "-----------------------------"
done < <(find "$source_errors_dir" -type f -name '*.err' -print0 | sort -z)

if [[ "$found_err" -eq 0 ]]; then
  echo "No .err files found under ${source_errors_dir}"
fi

rm -f "$errors_zip"
(
  cd "$DIR"
  zip -r "$(basename "$errors_zip")" "$(basename "$source_errors_dir")" > /dev/null
)

echo "Zipped errors directory to: $errors_zip"
echo 'You can download all workflow errors by from the "Results" tab.'
