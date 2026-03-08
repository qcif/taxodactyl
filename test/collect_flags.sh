#!/usr/bin/env bash

set -euo pipefail

usage() {
	echo "Usage: $0 <source_dir> <destination_dir>"
	echo "Finds 5.1.flag, 5.2.flag, 5.3.flag (real files only) under source_dir and copies them to destination_dir."
	echo "Each copied file is renamed to: <parent_folder>_<flag_filename>"
}

if [[ $# -ne 2 ]]; then
	usage
	exit 2
fi

source_dir="$1"
destination_dir="$2"

if [[ ! -d "$source_dir" ]]; then
	echo "Error: source directory does not exist: $source_dir" >&2
	exit 2
fi

mkdir -p "$destination_dir"

source_dir="$(cd "$source_dir" && pwd)"
destination_dir="$(cd "$destination_dir" && pwd)"

copied=0

while IFS= read -r -d '' file_path; do
	parent_dir_name="$(basename "$(dirname "$file_path")")"
	file_name="$(basename "$file_path")"
	target_name="${parent_dir_name}_${file_name}"
	target_path="$destination_dir/$target_name"

	if [[ -e "$target_path" ]]; then
		echo "Warning: target exists, skipping: $target_path" >&2
		continue
	fi

	cp "$file_path" "$target_path"
	copied=$((copied + 1))
done < <(
	find "$source_dir" -type f \( -name '5.1.flag' -o -name '5.2.flag' -o -name '5.3.flag' \) -print0
)

echo "Copied $copied file(s) to: $destination_dir"


# python3 /mnt/data/tests-wf-2/scripts/test_flags.py \
# blast_all/flags/ \
# /mnt/data/tests-wf-2/tests/class_1_main_v144dev_2202/flags/blast_all \
# > /mnt/data/tests-wf-2/tests/class_1_main_v144dev_2202/flags/blast_all_1331.txt

# python3 /mnt/data/tests-wf-2/scripts/test_flags.py \
# daff_shaun/flags/ \
# /mnt/data/tests-wf-2/tests/class_1_main_v144dev_2202/flags/daff_shaun \
# > /mnt/data/tests-wf-2/tests/class_1_main_v144dev_2202/flags/daff_shaun_1331.txt

# python3 /mnt/data/tests-wf-2/scripts/test_flags.py \
# daff_sydney/flags/ \
# /mnt/data/tests-wf-2/tests/main_v144dev_2202/flags/daff_sydney \
# > /mnt/data/tests-wf-2/tests/main_v144dev_2202/flags/daff_sydney_1331.txt

# python3 /mnt/data/tests-wf-2/scripts/test_flags.py \
# daff_scenarios/flags/ \
# /mnt/data/tests-wf-2/tests/main_v144dev_2202/flags/daff_scenarios \
# > /mnt/data/tests-wf-2/tests/main_v144dev_2202/flags/daff_scenarios_1331.txt
