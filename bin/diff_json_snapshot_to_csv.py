#!/usr/bin/env python3
"""Convert nf-test side-by-side snapshot diff text to a flat CSV.

Expected output columns:
- baseline_sample
- baseline_file
- baseline_md5
- actual_sample
- actual_file
- actual_md5

This parser targets the format produced in files like nf-test_errors.txt, where
changes are shown as side-by-side text with markers such as '|', '<', '>'.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict, deque
from pathlib import Path


SAMPLE_RE = re.compile(r'"(query_\d+_[^"]+)"')
FILE_MD5_RE = re.compile(r'"([^":]+):md5,([0-9a-fA-F]{32})"')
SAMPLE_NUM_RE = re.compile(r'query_(\d+)_[^"]+')


def sample_num(sample: str) -> int | None:
    match = SAMPLE_NUM_RE.fullmatch(sample)
    if not match:
        return None
    return int(match.group(1))


def split_diff_columns(line: str) -> tuple[str, str]:
    """Split a side-by-side diff line into left/right columns.

    Priority of separators:
    1) explicit vertical bar used in snapshot diffs
    2) insertion marker '>'
    3) deletion marker '<'
    """
    if "|" in line:
        left, right = line.split("|", 1)
        return left, right
    if ">" in line:
        left, right = line.split(">", 1)
        return left, right
    if "<" in line:
        left, right = line.split("<", 1)
        return left, right
    return line, ""


def parse_snapshot_diff(lines: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current_sample = ""
    current_channel_id = 1
    samples_seen_in_channel: set[str] = set()
    previous_sample_num: int | None = None

    # Each block corresponds to one contiguous sample region in the diff.
    blocks: list[dict[str, object]] = []
    active_block: dict[str, object] | None = None

    for line in lines:
        left_col, right_col = split_diff_columns(line)
        has_explicit_separator = ("|" in line) or (">" in line) or ("<" in line)

        left_samples = SAMPLE_RE.findall(left_col)
        right_samples = SAMPLE_RE.findall(right_col)
        found_sample = left_samples[-1] if left_samples else (right_samples[-1] if right_samples else "")

        if found_sample and found_sample != current_sample:
            found_sample_num = sample_num(found_sample)

            # Heuristic channel boundary detection:
            # - sample name repeats in a later section, or
            # - sample numeric order resets/decreases (e.g., 006 -> 001).
            if (
                found_sample in samples_seen_in_channel
                or (
                    previous_sample_num is not None
                    and found_sample_num is not None
                    and found_sample_num <= previous_sample_num
                )
            ):
                current_channel_id += 1
                samples_seen_in_channel.clear()
                previous_sample_num = None

            current_sample = found_sample
            found_sample_num = sample_num(found_sample)
            if found_sample_num is not None:
                previous_sample_num = found_sample_num
            samples_seen_in_channel.add(found_sample)
            active_block = {
                "sample": current_sample,
                "channel_id": current_channel_id,
                "baseline": [],
                "actual": [],
            }
            blocks.append(active_block)
        elif found_sample and active_block is None:
            current_sample = found_sample
            found_sample_num = sample_num(found_sample)
            if found_sample_num is not None:
                previous_sample_num = found_sample_num
            samples_seen_in_channel.add(found_sample)
            active_block = {
                "sample": current_sample,
                "channel_id": current_channel_id,
                "baseline": [],
                "actual": [],
            }
            blocks.append(active_block)

        if not current_sample or active_block is None:
            continue

        left_entries = FILE_MD5_RE.findall(left_col)
        right_entries = FILE_MD5_RE.findall(right_col)

        # Some lines contain both columns but no explicit separator marker.
        if not has_explicit_separator:
            all_entries = FILE_MD5_RE.findall(line)
            if len(all_entries) >= 2:
                left_entries = [all_entries[0]]
                right_entries = [all_entries[1]]

        baseline_entries: list[tuple[str, str]] = active_block["baseline"]  # type: ignore[assignment]
        actual_entries: list[tuple[str, str]] = active_block["actual"]  # type: ignore[assignment]

        baseline_entries.extend(left_entries)
        actual_entries.extend(right_entries)

    for block in blocks:
        sample = block["sample"]  # type: ignore[index]
        channel_id = str(block["channel_id"])  # type: ignore[index]
        baseline_entries: list[tuple[str, str]] = block["baseline"]  # type: ignore[assignment]
        actual_entries: list[tuple[str, str]] = block["actual"]  # type: ignore[assignment]

        actual_by_file: dict[str, deque[tuple[str, str]]] = defaultdict(deque)
        unmatched_actual: deque[tuple[str, str]] = deque()
        for a_file, a_md5 in actual_entries:
            actual_by_file[a_file].append((a_file, a_md5))
            unmatched_actual.append((a_file, a_md5))

        for b_file, b_md5 in baseline_entries:
            if actual_by_file[b_file]:
                matched_actual = actual_by_file[b_file].popleft()
                unmatched_actual.remove(matched_actual)
                a_file, a_md5 = matched_actual
            else:
                a_file, a_md5 = "", ""

            rows.append(
                {
                    "channel_id": channel_id,
                    "baseline_sample": sample,
                    "baseline_file": b_file,
                    "baseline_md5": b_md5,
                    "actual_sample": sample,
                    "actual_file": a_file,
                    "actual_md5": a_md5,
                }
            )

        for a_file, a_md5 in unmatched_actual:
            rows.append(
                {
                    "channel_id": channel_id,
                    "baseline_sample": sample,
                    "baseline_file": "",
                    "baseline_md5": "",
                    "actual_sample": sample,
                    "actual_file": a_file,
                    "actual_md5": a_md5,
                }
            )

    return rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = [
        "channel_id",
        "baseline_sample",
        "baseline_file",
        "baseline_md5",
        "actual_sample",
        "actual_file",
        "actual_md5",
        "result",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def add_result_column(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Append a result flag based on md5 equality.

    result is "true" when baseline_md5 and actual_md5 are equal and non-empty,
    otherwise "false".
    """
    enriched: list[dict[str, str]] = []
    for row in rows:
        baseline_md5 = row.get("baseline_md5", "")
        actual_md5 = row.get("actual_md5", "")
        result = "true" if baseline_md5 and baseline_md5 == actual_md5 else "false"
        enriched.append({**row, "result": result})
    return enriched


def write_summary_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    """Write per-channel/sample summary with difference counts."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        channel_id = row.get("channel_id", "")
        sample = row.get("baseline_sample", "") or row.get("actual_sample", "")
        if row.get("result", "false") == "false":
            counts[(channel_id, sample)] += 1

    fieldnames = ["channel_id", "sample", "difference_count"]
    with output_path.open("w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()
        for (channel_id, sample), diff_count in sorted(
            counts.items(),
            key=lambda item: (int(item[0][0]) if str(item[0][0]).isdigit() else 0, item[0][1]),
        ):
            writer.writerow(
                {
                    "channel_id": channel_id,
                    "sample": sample,
                    "difference_count": diff_count,
                }
            )


def keep_only_diffs(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep rows where baseline and actual are not identical.

    This retains:
    - baseline-only rows
    - actual-only rows
    - rows where file names differ
    - rows where md5 values differ
    """
    filtered: list[dict[str, str]] = []
    for row in rows:
        same_sample = row["baseline_sample"] == row["actual_sample"]
        same_file = row["baseline_file"] == row["actual_file"]
        same_md5 = row["baseline_md5"] == row["actual_md5"]
        if same_sample and same_file and same_md5:
            continue
        filtered.append(row)
    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert side-by-side JSON snapshot diff text to CSV"
    )
    parser.add_argument("input", type=Path, help="Path to diff text file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: input filename with .csv)",
    )
    parser.add_argument(
        "--only-diffs",
        action="store_true",
        help="Keep only rows where baseline and actual differ",
    )
    args = parser.parse_args()

    input_path: Path = args.input
    output_path: Path = args.output or input_path.with_suffix(".csv")

    lines = input_path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows = parse_snapshot_diff(lines)
    rows = add_result_column(rows)
    if args.only_diffs:
        rows = keep_only_diffs(rows)
    write_csv(rows, output_path)
    summary_path = output_path.with_name(f"{output_path.stem}_summary{output_path.suffix}")
    write_summary_csv(rows, summary_path)

    print(f"Wrote {len(rows)} rows to {output_path}")
    print(f"Wrote summary to {summary_path}")


if __name__ == "__main__":
    main()
