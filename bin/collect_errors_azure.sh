#!/usr/bin/bash

set -euo pipefail

usage() {
  echo "Usage: $0 --dir <directory> [--account-name <name>] [--container-name <name>]"
}

download_blob() {
  local blob_name="$1"
  local output_file="$2"

  if [[ -n "${AZURE_STORAGE_ACCOUNT_KEY:-}" ]]; then
    az storage blob download \
      --account-name "$AZURE_STORAGE_ACCOUNT_NAME" \
      --account-key "$AZURE_STORAGE_ACCOUNT_KEY" \
      --container-name "$AZURE_STORAGE_CONTAINER_NAME" \
      --name "$blob_name" \
      --file "$output_file" \
      --only-show-errors >/dev/null 2>&1
  else
    az storage blob download \
      --account-name "$AZURE_STORAGE_ACCOUNT_NAME" \
      --container-name "$AZURE_STORAGE_CONTAINER_NAME" \
      --name "$blob_name" \
      --file "$output_file" \
      --auth-mode login \
      --only-show-errors >/dev/null 2>&1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir)
      execution_folder="$2"
      shift 2
      ;;
    --account-name)
      AZURE_STORAGE_ACCOUNT_NAME="$2"
      shift 2
      ;;
    --container-name)
      AZURE_STORAGE_CONTAINER_NAME="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      shift
      ;;
  esac
done

AZURE_STORAGE_ACCOUNT_NAME="${AZURE_STORAGE_ACCOUNT_NAME:-${STORAGE_ACCOUNT_STD:-daffstandard}}"
AZURE_STORAGE_CONTAINER_NAME="${AZURE_STORAGE_CONTAINER_NAME:-${STORAGE_CONTAINER_WORK:-workdata}}"
AZURE_STORAGE_ACCOUNT_KEY="${AZURE_STORAGE_ACCOUNT_KEY:-${STORAGE_ACCOUNT_KEY:-${NXF_AZURE_STORAGE_KEY:-}}}"

if [[ -z "${AZURE_STORAGE_ACCOUNT_KEY:-}" && -n "${CACHE_AZURE_CONNECTION_STRING:-}" ]]; then
  AZURE_STORAGE_ACCOUNT_KEY="$(sed -nE 's/.*AccountKey=([^;]+).*/\1/p' <<< "$CACHE_AZURE_CONNECTION_STRING" | head -n 1)"
fi

if [[ -z "${execution_folder:-}" ]]; then
  usage
  exit 1
fi

if ! command -v az >/dev/null 2>&1; then
  echo "az CLI is required"
  exit 1
fi

if [[ -z "${AZURE_STORAGE_ACCOUNT_KEY:-}" ]]; then
  if ! az account show >/dev/null 2>&1; then
    echo "No storage account key found and no Azure CLI login session available"
    echo "Set AZURE_STORAGE_ACCOUNT_KEY (or CACHE_AZURE_CONNECTION_STRING) or run: az login"
    exit 1
  fi
fi

cd "$execution_folder" || exit 1

output_dir="$execution_folder/azure_errors"
mkdir -p "$output_dir"

declare -A process_by_hash
declare -A tag_by_hash
declare -A workdir_by_hash

mapfile -t failed_tasks < <(nextflow log last -f process,workdir,tag -F 'exit != 0')

if [[ ${#failed_tasks[@]} -eq 0 ]]; then
  echo "No failed tasks found"
  exit 0
fi

for task_row in "${failed_tasks[@]}"; do
  IFS=$'\t' read -r process workdir tag <<< "$task_row"

  if [[ -z "${workdir:-}" ]]; then
    continue
  fi

  short_hash="${workdir##*/}"
  short_hash="${short_hash:0:8}"

  process_by_hash["$short_hash"]="${process:-unknown}"
  tag_by_hash["$short_hash"]="${tag:-}"
  workdir_by_hash["$short_hash"]="$workdir"

  download_blob "$workdir/.command.out" "$output_dir/$short_hash.command.out" || true
  download_blob "$workdir/.command.err" "$output_dir/$short_hash.command.err" || true
  download_blob "$workdir/.command.sh" "$output_dir/$short_hash.command.sh" || true
  download_blob "$workdir/.exitcode" "$output_dir/$short_hash.exitcode" || true
done

echo ""
echo "Tasks with errors (non-empty .command.err):"

has_errors=false
shopt -s nullglob
for err_file in "$output_dir"/*.command.err; do
  if [[ -s "$err_file" ]]; then
    hash=$(basename "$err_file" .command.err)
    echo "Process: ${process_by_hash[$hash]:-unknown}"
    echo "Tag: ${tag_by_hash[$hash]:-}"
    echo "Workdir: ${workdir_by_hash[$hash]:-}"
    echo "Last 10 lines of stderr:"
    tail -n 10 "$err_file"

    out_file="$output_dir/$hash.command.out"
    if [[ -f "$out_file" ]]; then
      echo ""
      echo "Last 10 lines of stdout:"
      tail -n 10 "$out_file"
    fi

    echo "-----------------------------"
    has_errors=true
  fi
done
shopt -u nullglob

if [[ "$has_errors" == false ]]; then
  echo "  (none)"
fi
