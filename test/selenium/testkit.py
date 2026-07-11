#!/usr/bin/env python3

"""testkit — CLI companion to the Selenium report test suite.

Subcommands:

  ingest   Extract observed values from an HTML report and write a new
           expected/*.yaml fixture. Use on freshly generated reports that
           have been manually verified.

  promote  Merge observed values into an existing expected/*.yaml when
           legitimate drift is observed (e.g. new sequence records in
           the reference database).

Run from `test/selenium/` with the venv activated:

    python testkit.py ingest reports/3_report_FOO_2026-01-15_08_00_00.html
    python testkit.py promote 1_report_SME25-218_2025-12-11_07_30_03.yaml
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

from lib.collect import collect_all
from lib.driver import make_driver
from lib.promote import promote_yaml
from lib.report import Report


REPORTS_DIR = Path("reports")
EXPECTED_DIR = Path("expected")

PREFIX_RE = re.compile(r"^(\d+)_")


def _next_prefix() -> int:
    prefixes = []
    for p in EXPECTED_DIR.glob("*.yaml"):
        m = PREFIX_RE.match(p.name)
        if m:
            prefixes.append(int(m.group(1)))
    return (max(prefixes) + 1) if prefixes else 1


def _target_yaml_path(html_path: Path, prefix: int = None) -> Path:
    stem = html_path.stem
    if PREFIX_RE.match(stem):
        # HTML already has a prefix; mirror it in the YAML name.
        return EXPECTED_DIR / f"{stem}.yaml"
    if prefix is None:
        prefix = _next_prefix()
    return EXPECTED_DIR / f"{prefix}_{stem}.yaml"


def _ensure_html_in_reports(html_path: Path) -> Path:
    if html_path.parent.resolve() == REPORTS_DIR.resolve():
        return html_path
    target = REPORTS_DIR / html_path.name
    if not target.exists():
        shutil.copy2(html_path, target)
    return target


def _open_and_collect(html_path: Path, report: Report) -> None:
    driver = make_driver(headless=True)
    try:
        driver.get(html_path.resolve().as_uri())
        collect_all(driver, report)
    finally:
        driver.quit()


def cmd_ingest(args) -> int:
    html_path = Path(args.html).resolve()
    if not html_path.exists():
        print(f"error: {html_path} not found", file=sys.stderr)
        return 1

    target = (
        Path(args.out) if args.out
        else _target_yaml_path(html_path, prefix=args.prefix)
    )

    if target.exists() and not args.force:
        print(
            f"error: {target} already exists. Use `testkit promote "
            f"{target.name}` to merge drift, or pass --force to overwrite.",
            file=sys.stderr,
        )
        return 2

    reports_html = _ensure_html_in_reports(html_path)

    report = Report.from_schema(reports_html.name)
    _open_and_collect(reports_html, report)
    report.to_yaml(target, source="observed")

    print(f"Wrote {target}")
    print("Spot-check the values before committing.")
    return 0


def _resolve_yaml_target(target: str) -> Path:
    """Accept either 'foo.yaml', 'expected/foo.yaml', or a bare stem."""
    p = Path(target)
    if p.exists():
        return p
    stem = p.name
    if not stem.endswith(".yaml"):
        stem += ".yaml"
    candidate = EXPECTED_DIR / stem
    if candidate.exists():
        return candidate
    return p


def cmd_promote(args) -> int:
    if args.all:
        targets = sorted(EXPECTED_DIR.glob("*.yaml"))
        if not targets:
            print(f"error: no YAMLs found in {EXPECTED_DIR}", file=sys.stderr)
            return 1
    else:
        if not args.target:
            print(
                "error: provide a YAML name or --all",
                file=sys.stderr,
            )
            return 2
        target = _resolve_yaml_target(args.target)
        if not target.exists():
            print(f"error: {target} not found", file=sys.stderr)
            return 1
        targets = [target]

    reports_dir = Path(args.reports) if args.reports else REPORTS_DIR
    if not reports_dir.is_dir():
        print(f"error: {reports_dir} is not a directory", file=sys.stderr)
        return 1

    total = 0
    for path in targets:
        total += promote_yaml(
            path,
            reports_dir=reports_dir,
            headless=True,
            auto_yes=args.yes,
        )
    print(f"\nPromoted {total} assertion(s) across {len(targets)} file(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="testkit", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser(
        "ingest",
        help="Extract values from an HTML report into a new expected/*.yaml",
    )
    ingest.add_argument("html", help="Path to the generated HTML report")
    ingest.add_argument(
        "--prefix", type=int, default=None,
        help="Numeric prefix for the new YAML filename (default: next free)",
    )
    ingest.add_argument(
        "--out", default=None,
        help="Explicit path for the YAML output (overrides --prefix)",
    )
    ingest.add_argument(
        "--force", action="store_true",
        help="Overwrite an existing expected/*.yaml at the target path",
    )
    ingest.set_defaults(func=cmd_ingest)

    promote = sub.add_parser(
        "promote",
        help=(
            "Merge observed values into an existing expected/*.yaml when "
            "legitimate drift is observed"
        ),
    )
    promote.add_argument(
        "target", nargs="?",
        help="YAML name, path, or stem (unused with --all)",
    )
    promote.add_argument(
        "--all", action="store_true",
        help="Promote every YAML in expected/",
    )
    promote.add_argument(
        "--yes", action="store_true",
        help="Skip prompts and accept every drift (dangerous)",
    )
    promote.add_argument(
        "--reports", default=None,
        help=(
            "Directory to search for the HTML report (default: reports/). "
            "Reports are matched by sample_id when the exact filename is "
            "not present, so timestamps in the report filename may differ "
            "from the YAML fixture's."
        ),
    )
    promote.set_defaults(func=cmd_promote)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
