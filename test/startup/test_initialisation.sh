#!/usr/bin/env bash
# Run with: bash test/startup/test_initialisation.sh
# Requires Nextflow and its configured plugins; no containers or databases.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
evidence=$(mktemp -d "${TMPDIR:-/tmp}/taxodactyl-startup.XXXXXX")
printf 'Validation evidence: %s\n' "$evidence"
cd "$evidence"

guard='BOLD execution (--db_type bold) is temporarily disabled.'

check_case() {
    local name=$1 expected=$2
    shift 2
    local dir="$evidence/$name" status=0
    mkdir -p "$dir"
    local -a command=(nextflow -log "$dir/nextflow.log" run "$repo/main.nf" \
        -ansi-log false -work-dir "$dir/work" \
        --metadata "$repo/test/metadata.csv" \
        --sequences "$repo/test/query.fasta" \
        --taxdb "$evidence" --outdir "$dir/output" \
        --app_data_dir "$dir/app-data" --temp_root_dir "$dir/tmp" \
        --trace_file "$dir/trace.txt" --monochrome_logs true \
        "$@")
    printf 'RUN %s:' "$name"
    printf ' %q' "${command[@]}"
    printf '\n'
    "${command[@]}" > "$dir/console.log" 2>&1 || status=$?
    printf '%s\n' "$status" > "$dir/exit-status.txt"

    if [[ "$expected" == success ]]; then
        [[ "$status" == 0 ]] || { cat "$dir/console.log"; return 1; }
        if grep -Fq "$guard" "$dir/console.log"; then
            printf 'Unexpected BOLD rejection: %s\n' "$name" >&2
            return 1
        fi
    else
        [[ "$status" != 0 ]] || { printf 'Expected failure: %s\n' "$name" >&2; return 1; }
        grep -Fq -- "$expected" "$dir/console.log" || { cat "$dir/console.log"; return 1; }
    fi
    # No trace task rows, submissions, or process command scripts may exist.
    if [[ -f "$dir/trace.txt" ]] && ! awk 'NR > 1 && NF {exit 1}' "$dir/trace.txt"; then
        printf 'Unexpected trace task: %s\n' "$name" >&2
        return 1
    fi
    if grep -Eq 'Submitted process|Cached process' "$dir/nextflow.log"; then
        printf 'Unexpected process submission: %s\n' "$name" >&2
        return 1
    fi
    if [[ -d "$dir/work" ]] && [[ -n "$(find "$dir/work" -name .command.sh -print -quit)" ]]; then
        printf 'Unexpected process work: %s\n' "$name" >&2
        return 1
    fi
    printf 'PASS %s\n' "$name"
}

check_case bold_explicit "$guard" --db_type bold
check_case bold_test_profile "$guard" -profile test
check_case bold_before_coverage "$guard" --db_type bold --db_cov_min_a 1
check_case bold_without_schema "$guard" --db_type bold --validate_params false
check_case blast_missing_db "'blastdb' parameter must be set" --db_type blast_core_nt
check_case blast_coverage "'db_cov_min_a' parameter must be greater" \
    --db_type blast_core_nt --blastdb "$evidence/subset_core_nt" --db_cov_min_a 1
check_case blast_related_coverage "'db_cov_related_min_a' parameter must be greater" \
    --db_type blast_core_nt --blastdb "$evidence/subset_core_nt" --db_cov_related_min_a 10
# Preview exercises the real entry point and workflow construction, not analysis.
check_case blast_startup_preview success -preview \
    --db_type blast_core_nt --blastdb "$evidence/subset_core_nt"
