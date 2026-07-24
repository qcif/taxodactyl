"""Promote observed values into an existing expected/*.yaml.

Used by `testkit promote` when legitimate drift is observed (e.g. new
sequence records deposited in the reference database).

Flow:
    1. Load the existing YAML via parse_yaml (`.expected` populated).
    2. Open the matching HTML and run collect_all (`.observed` populated).
    3. For each drifted assertion, prompt the user [y/n/a/q] with old vs new.
    4. For accepted drifts, update the assertion's raw_value in-place.
    5. Back up the previous YAML into expected/.backups/ (keep last 3).
    6. Rewrite the YAML via Report.to_yaml(source='expected').
    7. Replace the reference HTML in expected/reports/ with the observed one.
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

from lib.collect import collect_all
from lib.driver import make_driver
from lib.report import extract_report_date, find_report_html, parse_yaml


DEFAULT_REPORTS_DIR = Path("expected/reports")
BACKUP_DIR = Path("expected/.backups")
BACKUPS_TO_KEEP = 3
REFERENCE_DIR = Path("expected/reports")


def _prompt(context: str) -> str:
    try:
        return input(context)
    except EOFError:
        return "q"


def _decide(prompt_state: dict) -> bool:
    """Ask the user; mutate state (accept_all, quit) as needed. Return
    whether to accept the current diff."""
    if prompt_state["quit"]:
        return False
    if prompt_state["accept_all"]:
        return True
    while True:
        choice = _prompt("    accept? [y]es / [n]o / [a]ll / [q]uit: ")
        c = (choice or "").strip().lower()
        if c in ("", "n"):
            return False
        if c == "y":
            return True
        if c == "a":
            prompt_state["accept_all"] = True
            return True
        if c == "q":
            prompt_state["quit"] = True
            return False


def _backup(yaml_path: Path) -> Path:
    """Copy `yaml_path` into BACKUP_DIR with a timestamp suffix and rotate
    older backups so at most BACKUPS_TO_KEEP remain for this fixture."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stem = yaml_path.stem
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup = BACKUP_DIR / f"{stem}.{ts}.yaml"
    shutil.copy2(yaml_path, backup)

    existing = sorted(
        BACKUP_DIR.glob(f"{stem}.*.yaml"),
        key=lambda p: p.name,
        reverse=True,
    )
    for old in existing[BACKUPS_TO_KEEP:]:
        old.unlink()

    return backup


def _update_reference_html(
    yaml_path: Path, sample_id: str, observed_html: Path,
) -> Path:
    """Replace the reference HTML for `sample_id` with `observed_html`.

    The destination filename mirrors the fixture YAML stem so timestamps
    are not embedded: e.g. `1_SME25-218.html`.  Any existing reference
    HTML for this sample_id is removed first.  Returns the destination path.
    """
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    old = find_report_html(sample_id, REFERENCE_DIR)
    if old:
        old.unlink()
    dest = REFERENCE_DIR / f"{yaml_path.stem}.html"
    shutil.copy2(observed_html, dest)
    return dest


def promote_yaml(
    yaml_path: Path,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    headless: bool = True,
    auto_yes: bool = False,
) -> int:
    """Promote drifted observed values into `yaml_path`. Returns the number
    of assertions written back."""
    report = parse_yaml(yaml_path)
    html_path = find_report_html(report.sample_id, reports_dir)
    if html_path is None:
        print(
            f"error: no HTML report for sample_id '{report.sample_id}' "
            f"found in {reports_dir} (referenced by {yaml_path.name})",
            file=sys.stderr,
        )
        return 0

    driver = make_driver(headless=headless)
    try:
        driver.get(html_path.resolve().as_uri())
        collect_all(driver, report)
    finally:
        driver.quit()

    drifted = report.drifted()
    if not drifted:
        print(f"{yaml_path.name}: no drift detected.")
        return 0

    print(f"{yaml_path.name}: {len(drifted)} drifted assertion(s).")
    state = {"accept_all": auto_yes, "quit": False}
    accepted = 0

    for a in drifted:
        new_value = a.observed_for_yaml()
        print(
            f"\n  [{a.component}.{a.assertion_id}] ({a.assertion_type})"
        )
        print(f"    expected: {a.expected!r}")
        print(f"    observed: {new_value!r}")
        if _decide(state):
            a.raw_value = new_value
            accepted += 1
        if state["quit"]:
            break

    if accepted:
        backup = _backup(yaml_path)
        html_date = extract_report_date(html_path.name)
        if html_date:
            report.date = html_date
        report.to_yaml(yaml_path, source="expected")
        ref_html = _update_reference_html(
            yaml_path, report.sample_id, html_path
        )
        try:
            backup_label = backup.relative_to(Path.cwd())
            ref_label = ref_html.relative_to(Path.cwd())
        except ValueError:
            backup_label = backup
            ref_label = ref_html
        print(
            f"\n{yaml_path.name}: wrote {accepted} update(s). "
            f"Backup: {backup_label} | Reference HTML: {ref_label}"
        )
    else:
        print(f"\n{yaml_path.name}: no changes written.")

    return accepted
