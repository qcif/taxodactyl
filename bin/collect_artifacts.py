#!/usr/bin/env python3

"""Copy or link nf workdirs from trace.csv etc. for upload or debug. 

Identifies failed, aborted, or inconsistent tasks from:
    trace.csv
        FAILED or ABORTED tasks
        File is generated during Nextflow run
    flag_results.txt
        Tasks responsible for different flags different to test baseline flags
        File is generated using test_flags.py during nf-test.yml 
    nf-test_errors_summary.csv
        Tasks responsible for changes to nf-test snapshot from baseline. 
        File is a summary of nf-test_errors.txt created with diff_json_snapshot_to_csv.py
        
"Errored" task workdirs are then copied for upload (GH runner) or linked (self-
hosted runner) formatted as <task_name>/<sample_id> to allow for easy debugging. 

Usage:
    collect_artifacts.py <trace.csv> \
        --outdir <destination> \
        --flags_results <flags_results.txt> \
        --nft_errors <nf-test_errors_summary.csv>
        --mode <copy | link>

Arguments:
	trace_file   Path the the input trace.csv file.
    -o, --outdir  (Optional. Default = pwd). Path where workdirs will be copied.
    -f, --flags_results (Optional) Path to the flag_results.txt file. 
    -n, --nft_errors (Optional) Path to the nf-test_errors_summary.csv file. 
    -m, --mode (Optional. Default = copy). Choose to "copy" or "link" files. 
"""
import argparse
import csv
import os
from pathlib import Path
import shutil

def get_failed_tasks(trace_file: Path) -> dict:
    """
    Scans trace.csv for FAILED and ABORTED tasks.
    
    Args:
        trace_file: str or Path of trace.csv file to be scanned. 

    Returns:
        A list of tuples where the first value is the errored task and the second 
        is the sample_id.
    """
    errors = []
    try:
        with open(trace_file, mode="r", encoding="utf-8") as f_in:
            print(f"Scanning {trace_file} for FAILED or ABORTED tasks.")
            reader = csv.DictReader(f_in, delimiter="\t")
            for row in reader: 
                if row["status"] not in ["COMPLETED", "CACHED"]:
                    name = row["name"]
                    task = name.split()[0].replace("TAXODACTYL:", "")
                    sample_id = name.split()[1].replace("(", "").replace(")", "")
                    errors.append((task, sample_id))
            return errors
    except FileNotFoundError:
        print(f"Error: Input file {trace_file} not found.")

def get_errored_flags(flags_results: Path) -> dict:
    """
    Scans flags_results.txt for sample_id of errored flags.
    
    Args:
        flags_results: str or Path to flags_results.txt file to be scanned. 

    Returns:
        A list of tuples where the first value is the errored task and the second 
        is the sample_id.
        Note: For flags, the errored task is always "EVALUATE_DATABASE_COVERAGE".
    """
    task = "EVALUATE_DATABASE_COVERAGE"
    errors = []
    try:
        with open(flags_results, mode="r", encoding="utf-8") as f_in:
            print(f"Scanning {flags_results} for errored or changed flags.")
            for row in f_in:
                cols = row.split()
                if len(cols) >= 1 and cols[0].strip() == "[DIFF]":
                    sample_id = cols[1].strip()[:-9]
                    errors.append((task, sample_id))
            return errors
    except FileNotFoundError:
        print(f"Error: Input file {flags_results} not found.")

def get_nft_errors(nft_errors: str | Path) -> dict:
    """
    Scans nf-test_errors_summary.csv, collates sample IDs and matches to errored
    task. 
    
    Args:
        nft_errors: str or Path to nf-test_errors_summary.csv file to be scanned. 

    Returns:
      A list of tuples where the first value is the errored task and the second
      is the sample ID.
    """
    channel_to_task = {"1" : "EXTRACT_HITS",
                       "2" : "EXTRACT_CANDIDATES",
                       "3" : "EVALUATE_SOURCE_DIVERSITY",
                       "4" : "EVALUATE_DATABASE_COVERAGE"
                       }

    errors = set()
    try:
        with open(nft_errors, mode="r", encoding="utf-8") as f_in:
            print(f"Scanning {nft_errors} for snapshot deviation tasks.")
            # DictReader handles the header mapping automatically
            reader = csv.DictReader(f_in)
            for row in reader:
                channel = row["channel_id"]
                task = channel_to_task.get(channel)
                sample_id = row["sample"]
                errors.add((task, sample_id))
            return list(errors)
    except FileNotFoundError:
        print(f"Error: Input file {nft_errors} not found.")

def get_workdir(trace_file: str | Path, errors: list[tuple[str, str]]) -> dict[Path, Path]:
    """
    Scans trace.csv for list of errors provided and returns dict mapping error to workdir Path. 

    Args:
        trace_file: str or Path of trace.csv file to be scanned. 
        errors: list of tuples where the first value is the task and the second 
        is the sample_id.

    Returns:
        A dictionary mapping a relative file path consisting of <task>/<sample_id>
        to a workdir file path from the trace.csv file.
    """
    workdirs = {}
    try:
        with open(trace_file, mode="r", encoding="utf-8") as f_in:
            print(f"Collecting workdirs from {trace_file} for errors.")
            # DictReader handles the header mapping automatically
            reader = csv.DictReader(f_in, delimiter="\t")
            for row in reader:
                name = row["name"]
                task = name.split()[0].replace("TAXODACTYL:", "")
                sample_id = name.split()[1].replace("(", "").replace(")", "")
                for error in errors:
                    if task == error[0] and sample_id == error[1]:
                        workdirs[Path(f"{task}/{sample_id}")] = Path(row["workdir"])
            return workdirs
    except FileNotFoundError:
        print(f"Error: Input file {trace_file} not found.")

def copy_dirs(workdirs: dict[Path:Path], outdir: Path) -> None:
    """
    Uses shutil.copytree to copy workdirs to outdir with <task>/<sample_id> structure.

    Args:
        workdirs: dict mapping workdir file path from the trace.csv file to 
        a relative file path consisting of <task>/<sample_id>.

    Returns:
        None
    """
    for src, dest in workdirs.items():
        try:
            full_dest = outdir.joinpath(dest)
            # Debug line to be removed
            print(f"Attempting to copy: {src} -> {full_dest}")
            shutil.copytree(src, full_dest, dirs_exist_ok=True)
            print(f"Copied: {src} -> {full_dest}")
        except FileNotFoundError:
            print(f"Error: Source directory does not exist: {src}")
        except PermissionError:
            print(f"Error: Permission denied for {src} or {outdir}")

def link_dirs(workdirs: dict[Path:Path], outdir: Path) -> None:
    """
    Uses os.symlink to link workdirs to outdir with <task>/<sample_id> structure.

    Args:
        workdirs: dict mapping workdir file path from the trace.csv file to 
        a relative file path consisting of <task>/<sample_id>.
        outdir: 

    Returns:
        None
    """
    for src, dest in workdirs.items():
        full_dest = outdir.joinpath(dest)
        # Create parent directories for the destination
        full_dest.parent.mkdir(parents = True, exist_ok = True)
    # Include this if the errors don't show it anyway
    # if not src.exists():
    #     print(f"Error: Source directory does not exist: {src}"")
    
        try:
            # Debug line to be removed
            print(f"Attempting to link: {src} -> {full_dest}")
            os.symlink(src, full_dest, target_is_directory = True)
            print(f"Copied: {src} -> {full_dest}")
        except FileExistsError:
            print(f"Warning: Destination link already exists: {full_dest}")
        except PermissionError:
            print(f"Permission denied: Cannot create link at {full_dest}.")

def main():
    """
    Parses command-line arguments, r...

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "trace_file", 
        type = str,
        help = "Path to the trace.csv input file."
    )

    parser.add_argument(
        "-o", "--outdir", 
        type = str,
        default = os.getcwd(),
        help = "Path to directory where workdir files will be copied (default: pwd)."
    )

    parser.add_argument(
        "-f", "--flags_results", 
        type = str,
        help = "Path to flags_results.txt file."
    )

    parser.add_argument(
        "-n", "--nft_errors", 
        type = str,
        help = "Path to nf-test_errors_summary.csv file."
    )

    parser.add_argument(
        "-m", "--mode",
        choices = ["copy", "link"],
        default = "copy",
        help = "Choose to copy (cp) or link (ln -s) files to outdir (default: copy)."
    )

    args = parser.parse_args()

    trace_file = Path(args.trace_file)
    outdir = Path(args.outdir)
    flags_results = Path(args.flags_results) if args.flags_results else None
    nft_errors = Path(args.nft_errors) if args.nft_errors else None
    mode = args.mode

    collected_errors = []
    collected_errors.extend(get_failed_tasks(trace_file))
    if flags_results is not None:
        collected_errors.extend(get_errored_flags(flags_results))
    if nft_errors is not None:
        collected_errors.extend(get_nft_errors(nft_errors))

    error_workdirs = get_workdir(trace_file, collected_errors)
    if mode == "copy":
        copy_dirs(error_workdirs, outdir)
    if mode == "link":
        link_dirs(error_workdirs, outdir)

    print("Finished!")


if __name__ == "__main__":
    main()
