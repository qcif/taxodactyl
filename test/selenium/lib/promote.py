"""Promote observed values into an existing expected/*.yaml.

Used by `testkit promote` when legitimate drift is observed (e.g. new
sequence records deposited in the reference database).

Flow:
    1. Load the existing YAML via parse_yaml (`.expected` populated).
    2. Open the matching HTML and run collect_all (`.observed` populated).
    3. For each drifted assertion, prompt the user [y/n/a/q] with old vs new.
    4. For accepted drifts, update the assertion's raw_value in-place.
    5. Rewrite the YAML via Report.to_yaml(source='expected').
"""

import sys
from pathlib import Path

from lib.collect import collect_all
from lib.driver import make_driver
from lib.report import find_report_html, parse_yaml


DEFAULT_REPORTS_DIR = Path("expected/reports")


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
        report.to_yaml(yaml_path, source="expected")
        print(f"\n{yaml_path.name}: wrote {accepted} update(s).")
    else:
        print(f"\n{yaml_path.name}: no changes written.")

    return accepted
