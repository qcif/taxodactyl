#!/usr/bin/env python3
"""Integration-test fixture management CLI.

Kept deliberately separate from ``run_tests.sh``: this is a fixture-management
entrypoint, not a test runner.

Invoke directly::

    scripts/tests/integration/testkit.py <subcommand> [...]

Sub-commands:

- ``harvest`` — scaffold a new case directory from a Nextflow workflow run.
- ``promote`` — copy a produced ``db_coverage.json`` into ``<case>/expected/``
  after reviewing the semantic diff.
- ``seed`` — like ``promote`` but for a case with no fixture yet; no diff step.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Ensure ``scripts/`` is importable when the file is executed directly, so
# ``from tests.integration.kit.coverage_assert import …`` resolves the same
# way it does under ``python -m``.
_SCRIPTS_ROOT = str(Path(__file__).resolve().parents[2])
if _SCRIPTS_ROOT not in sys.path:
    sys.path.insert(0, _SCRIPTS_ROOT)

from tests.integration.kit.coverage_assert import (  # noqa: E402
    Change,
    ChangeKind,
    semantic_diff,
)
from tests.integration.kit.harvest import (  # noqa: E402
    HarvestError,
    RemotePath,
    harvest,
)
from tests.integration.test_integration import (  # noqa: E402
    DB_COVERAGE_FILENAME,
    EXPECTED_DIR,
    TEMPDIR_PREFIX,
)

# ``__file__`` may be a symlink (e.g. ``testkit.py`` symlinked into
# ``$PATH`` or the repo root). Resolve it so we walk from the real file
# location — otherwise ``parents[2]`` climbs above the symlink's directory
# and TEST_CASE_ROOT ends up pointing outside the repo.
PYTHON_ROOT = Path(__file__).resolve().parents[2]
TEST_CASE_ROOT = PYTHON_ROOT / "tests/test-data/integration/blast"

USE_COLOUR = sys.stdout.isatty()
RED = "\033[31m" if USE_COLOUR else ""
GREEN = "\033[32m" if USE_COLOUR else ""
YELLOW = "\033[33m" if USE_COLOUR else ""
CYAN = "\033[36m" if USE_COLOUR else ""
BOLD = "\033[1m" if USE_COLOUR else ""
RESET = "\033[0m" if USE_COLOUR else ""


class ToolkitError(Exception):
    """Raised for user-facing errors — printed without a traceback."""


@dataclass
class CasePlan:
    """Everything the promote/seed workflow needs for a single case."""
    name: str
    produced: Path
    fixture: Path
    changes: list[Change]

    @property
    def has_fixture(self) -> bool:
        return self.fixture.exists()

    @property
    def would_fail_changes(self) -> list[Change]:
        return [c for c in self.changes if c.kind is ChangeKind.WOULD_FAIL]

    @property
    def dropped_species_changes(self) -> list[Change]:
        """WOULD_FAIL entries that would remove an analysis-target key."""
        return [
            c for c in self.would_fail_changes
            if c.reason == "missing required key"
        ]


# ---------------------------------------------------------------------------
# Source-directory discovery
# ---------------------------------------------------------------------------

def _resolve_source_dir(from_arg: Path | None) -> Path:
    """Return the run directory to promote from.

    Falls back to the most recently modified ``integration_test_*`` directory
    under the system temp dir when ``--from`` is not given.
    """
    if from_arg is not None:
        src = from_arg.expanduser().resolve()
        if not src.is_dir():
            raise ToolkitError(f"--from path is not a directory: {src}")
        return src

    tmp_root = Path(tempfile.gettempdir())
    candidates = [
        p for p in tmp_root.glob(f"{TEMPDIR_PREFIX}*")
        if p.is_dir()
    ]
    if not candidates:
        raise ToolkitError(
            f"No {TEMPDIR_PREFIX}* directory found under {tmp_root}."
            " Re-run the integration suite with --keep, or pass --from."
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _locate_produced_coverage(case_run_dir: Path) -> Path | None:
    """Return the ``db_coverage.json`` produced for a case, if any.

    The integration harness writes it to ``<case>/query_*/db_coverage.json``.
    """
    matches = sorted(case_run_dir.glob(f"query_*/{DB_COVERAGE_FILENAME}"))
    if not matches:
        return None
    # There's exactly one query_* dir per case for the current suite, but be
    # explicit about the choice for future multi-query cases.
    return matches[0]


# ---------------------------------------------------------------------------
# Case-plan construction
# ---------------------------------------------------------------------------

def _build_case_plan(name: str, source_dir: Path) -> CasePlan:
    case_run_dir = source_dir / name
    if not case_run_dir.is_dir():
        raise ToolkitError(
            f"Case '{name}' not found in run directory: {case_run_dir}"
        )
    produced = _locate_produced_coverage(case_run_dir)
    if produced is None:
        raise ToolkitError(
            f"Case '{name}' has no produced {DB_COVERAGE_FILENAME}"
            f" under {case_run_dir}. The last run likely raised an"
            " exception before P5 completed — fix the failure before"
            " promoting."
        )
    fixture = TEST_CASE_ROOT / name / EXPECTED_DIR / DB_COVERAGE_FILENAME
    changes: list[Change] = []
    if fixture.exists():
        with open(fixture) as f:
            expected = json.load(f)
        with open(produced) as f:
            actual = json.load(f)
        changes = semantic_diff(expected, actual)
    return CasePlan(name=name, produced=produced, fixture=fixture,
                    changes=changes)


def _select_case_names(
    args: argparse.Namespace,
    source_dir: Path,
) -> list[str]:
    """Resolve --case / --all / --all-failed to a list of case names."""
    if args.case:
        return [args.case]
    all_cases = sorted(
        p.name for p in source_dir.iterdir()
        if p.is_dir() and (TEST_CASE_ROOT / p.name).is_dir()
    )
    if args.all:
        return all_cases
    # --all-failed: only cases whose produced JSON currently fails the walker.
    failing = []
    for name in all_cases:
        try:
            plan = _build_case_plan(name, source_dir)
        except ToolkitError:
            continue
        if plan.has_fixture and plan.would_fail_changes:
            failing.append(name)
    return failing


# ---------------------------------------------------------------------------
# Diff rendering
# ---------------------------------------------------------------------------

def _render_diff(plan: CasePlan) -> None:
    if not plan.has_fixture:
        print(f"{CYAN}[{plan.name}]{RESET}"
              f" no existing fixture — will be created fresh.")
        return
    if not plan.changes:
        print(f"{CYAN}[{plan.name}]{RESET}"
              f" {GREEN}no changes vs. fixture.{RESET}")
        return
    print(f"{CYAN}[{plan.name}]{RESET} semantic diff ({len(plan.changes)}"
          " change(s)):")
    for c in plan.changes:
        if c.kind is ChangeKind.WOULD_FAIL:
            tag = f"{RED}{BOLD}WOULD_FAIL{RESET}"
        else:
            tag = f"{YELLOW}TOLERATED{RESET}"
        print(f"  {tag}  {c.path}: {c.reason}")


# ---------------------------------------------------------------------------
# Write step (shared by promote and seed)
# ---------------------------------------------------------------------------

def _confirm(prompt: str, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    reply = input(f"{prompt} [y/N] ").strip().lower()
    return reply in ("y", "yes")


def _write_fixture(plan: CasePlan, *, dry_run: bool) -> None:
    plan.fixture.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        print(f"  {YELLOW}(dry){RESET} would copy {plan.produced}"
              f" -> {plan.fixture}")
        return
    shutil.copy2(plan.produced, plan.fixture)
    rel = plan.fixture.relative_to(PYTHON_ROOT.parent)
    print(f"  {GREEN}wrote{RESET} {plan.fixture}")
    print(f"  {BOLD}git add {rel}{RESET}")


# ---------------------------------------------------------------------------
# Sub-command: promote
# ---------------------------------------------------------------------------

def cmd_promote(args: argparse.Namespace) -> int:
    source_dir = _resolve_source_dir(args.from_dir)
    print(f"Promoting from: {source_dir}")

    names = _select_case_names(args, source_dir)
    if not names:
        raise ToolkitError(
            "No cases selected. Use --case NAME, --all, or --all-failed"
            " (which requires cases currently failing the walker)."
        )

    plans: list[CasePlan] = []
    for name in names:
        try:
            plans.append(_build_case_plan(name, source_dir))
        except ToolkitError as exc:
            print(f"{RED}[{name}] skipped:{RESET} {exc}")

    if not plans:
        raise ToolkitError("No promotable cases after guardrail checks.")

    promoted = 0
    for plan in plans:
        print()
        _render_diff(plan)

        if plan.has_fixture and not plan.changes:
            print(f"  {GREEN}skipping — nothing to promote.{RESET}")
            continue

        if plan.dropped_species_changes:
            print(f"  {YELLOW}{BOLD}warning:{RESET} promotion would drop"
                  f" {len(plan.dropped_species_changes)} species key(s)"
                  " from the fixture.")
            if not _confirm(
                f"  Drop species keys for '{plan.name}'?",
                assume_yes=args.yes,
            ):
                print(f"  {YELLOW}skipped.{RESET}")
                continue

        prompt = (f"  Promote '{plan.name}' to"
                  f" {plan.fixture.relative_to(PYTHON_ROOT.parent)}?")
        if not _confirm(prompt, assume_yes=args.yes):
            print(f"  {YELLOW}skipped.{RESET}")
            continue

        _write_fixture(plan, dry_run=args.dry_run)
        promoted += 1

    print()
    if promoted == 0:
        print(f"{YELLOW}No fixtures promoted.{RESET}")
        return 1
    print(f"{GREEN}Promoted {promoted} fixture(s).{RESET}")
    return 0


# ---------------------------------------------------------------------------
# Sub-command: seed
# ---------------------------------------------------------------------------

def cmd_seed(args: argparse.Namespace) -> int:
    if not args.case:
        raise ToolkitError("seed requires --case NAME.")
    source_dir = _resolve_source_dir(args.from_dir)
    print(f"Seeding from: {source_dir}")

    plan = _build_case_plan(args.case, source_dir)
    if plan.has_fixture:
        raise ToolkitError(
            f"Fixture already exists at {plan.fixture}."
            " Use `promote` to update it."
        )
    print(f"{CYAN}[{plan.name}]{RESET} seeding fresh fixture from"
          f" {plan.produced}")

    prompt = (f"  Seed '{plan.name}' fixture at"
              f" {plan.fixture.relative_to(PYTHON_ROOT.parent)}?")
    if not _confirm(prompt, assume_yes=args.yes):
        print(f"{YELLOW}Aborted.{RESET}")
        return 1

    _write_fixture(plan, dry_run=args.dry_run)
    return 0


# ---------------------------------------------------------------------------
# Sub-command: harvest (Phase 5)
# ---------------------------------------------------------------------------

def cmd_harvest(args: argparse.Namespace) -> int:
    # If the log is remote, let the three optional flags inherit its
    # host by default — the common case is that all four share a host.
    outdir = (
        args.outdir.with_host_from(args.log)
        if args.outdir is not None else None
    )
    trace = (
        args.trace.with_host_from(args.log)
        if args.trace is not None else None
    )
    work_dir = (
        args.work_dir.with_host_from(args.log)
        if args.work_dir is not None else None
    )
    try:
        result = harvest(
            log=args.log,
            query_id=args.query,
            case_name=args.name,
            case_root=TEST_CASE_ROOT,
            dry_run=args.dry_run,
            assume_yes=args.yes,
            work_dir=work_dir,
            outdir=outdir,
            trace=trace,
        )
    except HarvestError as exc:
        raise ToolkitError(str(exc)) from exc

    if args.dry_run:
        print(f"{YELLOW}(dry){RESET} no files written.")
        return 0

    print()
    print(f"{GREEN}Harvested {len(result.written)} file(s) into"
          f" {result.case_dir}.{RESET}")
    print(
        f"\nNext: `run_tests.sh --keep RUN_TEST_CASE={args.name}` to smoke"
        f" test the case, then `testkit.py seed --case {args.name}` once"
        " the coverage output looks right.\n"
    )
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _add_shared_flags(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts.",
    )
    sub.add_argument(
        "--dry",
        dest="dry_run",
        action="store_true",
        help="Report what would happen without writing any files.",
    )


def _add_from_flag(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--from",
        dest="from_dir",
        type=Path,
        default=None,
        help=(
            "Directory containing per-case run outputs."
            f" Defaults to the most recent {TEMPDIR_PREFIX}* dir under"
            " the system temp directory."
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testkit",
        description=(
            "Manage integration-test fixtures for db_coverage.json."
            " All sub-commands read from a previous integration test run"
            " output directory (by default, the most recent"
            " integration_test_* dir under the system temp dir) — so you"
            " must have run the suite first, ideally with `run_tests.sh"
            " --keep`, before invoking this tool. Sub-commands: harvest"
            " (scaffold a case), seed (write a first-time fixture for a"
            " new case), promote (update an existing fixture after"
            " reviewing the semantic diff)."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # promote
    promote = subparsers.add_parser(
        "promote",
        help="Update an existing fixture from a previous run output.",
        description=(
            "Update an existing expected/db_coverage.json fixture using the"
            " db_coverage.json produced by a previous integration test run."
            " Reads by default from the most recent integration_test_* dir"
            " under the system temp dir, so `run_tests.sh --keep` (or an"
            " equivalent recent run) must have completed first. Renders a"
            " colour-coded semantic diff (WOULD_FAIL vs TOLERATED), prompts"
            " for confirmation, and warns before dropping species keys."
            " Refuses cases whose last run raised an exception (no produced"
            " file)."
        ),
    )
    target = promote.add_mutually_exclusive_group(required=True)
    target.add_argument("--case", help="Promote a single named case.")
    target.add_argument(
        "--all",
        action="store_true",
        help="Promote every case with a produced output.",
    )
    target.add_argument(
        "--all-failed",
        dest="all_failed",
        action="store_true",
        help="Promote only cases whose current run fails the walker.",
    )
    _add_from_flag(promote)
    _add_shared_flags(promote)
    promote.set_defaults(func=cmd_promote)

    # seed
    seed = subparsers.add_parser(
        "seed",
        help="Write a first-time fixture from a previous run output.",
        description=(
            "Write a first-time expected/db_coverage.json fixture for a case"
            " that does not yet have one, using the db_coverage.json produced"
            " by a previous integration test run. Reads by default from the"
            " most recent integration_test_* dir under the system temp dir,"
            " so `run_tests.sh --keep` (or an equivalent recent run) must"
            " have completed first. No diff step — this is the 'trust the"
            " first run' path. Refuses if the fixture already exists; use"
            " `promote` in that case."
        ),
    )
    seed.add_argument(
        "--case",
        required=True,
        help='Case name to seed (e.g. "c01").')
    _add_from_flag(seed)
    _add_shared_flags(seed)
    seed.set_defaults(func=cmd_seed)

    # harvest
    harvest_parser = subparsers.add_parser(
        "harvest",
        help="Scaffold a new case dir from a completed NF run.",
        description=(
            "Scaffold a new integration test case dir from a completed"
            " Nextflow run. Takes the run's .nextflow.log as the sole"
            " source arg — the first line encodes the profile"
            " (local/singularity/azure) and the outdir, and the"
            " pipeline_info/execution_trace_*.txt under that outdir gives"
            " the per-task workdir URI. Files that live only in a task"
            " scratch dir (metadata.csv, sequences.fasta, taxids.csv,"
            " taxonomy.csv, candidates_phylogeny.nwk) are fetched"
            " individually — Azure runs pull each blob one at a time,"
            " never mirroring the whole workdir. blast_result.xml,"
            " query.fasta and metadata.csv are filtered down to the"
            " single --query <sample-id> so the case becomes a"
            " single-query snapshot. Refuses if a case of --name already"
            " exists under scripts/tests/test-data/integration/blast/."
        ),
    )
    harvest_parser.add_argument(
        "log",
        type=RemotePath,
        help=(
            "Path to the run's .nextflow.log. May be either a local path"
            " or `host:path` for a run on a remote SSH host (e.g."
            " `daff-admin:/mnt/data/.../nextflow.log`)."
        ),
    )
    harvest_parser.add_argument(
        "--query",
        required=True,
        help=(
            "Which query to snapshot. Accepts either a sample_id"
            " (e.g. 'VE24-1351_COI') matching a metadata.csv row and a"
            " <Iteration_query-def> prefix in blast_result.xml, or a"
            " 1-3 digit query index (e.g. '3' or '003') — resolved to a"
            " sample_id via the run's per-query task tags."
        ),
    )
    harvest_parser.add_argument(
        "--name",
        required=True,
        help=(
            "Case name to create under"
            " scripts/tests/test-data/integration/blast/<name>/."
            " Must not collide with an existing case dir."
        ),
    )
    harvest_parser.add_argument(
        "--work-dir",
        dest="work_dir",
        type=RemotePath,
        default=None,
        help=(
            "Override the workdir base if the log's workDir paths are"
            " stale (e.g. a run copied off its original machine). Each"
            " task's <hash-prefix>/<hash-tail> is joined to this path"
            " instead. Accepts local paths or `host:path`; a plain path"
            " inherits the log's host when the log is remote."
        ),
    )
    harvest_parser.add_argument(
        "--outdir",
        dest="outdir",
        type=RemotePath,
        default=None,
        help=(
            "Override the run's outdir. By default it's read from the"
            " launcher line's `--outdir`, or from the `outdir` field of"
            " a `-params-file` JSON. Accepts local paths or `host:path`;"
            " a plain path inherits the log's host when the log is"
            " remote. Useful when the log's paths are stale, when the"
            " outdir sits at a non-default location (e.g. Cloudgene job"
            " dirs), or when it lives on the same SSH host as the log."
        ),
    )
    harvest_parser.add_argument(
        "--trace",
        dest="trace",
        type=RemotePath,
        default=None,
        help=(
            "Override the execution trace path. By default it's read"
            " from `-with-trace` in the launcher line, or from"
            " `<outdir>/pipeline_info/execution_trace_*.txt`. Accepts"
            " local paths or `host:path`; a plain path inherits the"
            " log's host when the log is remote."
        ),
    )
    _add_shared_flags(harvest_parser)
    harvest_parser.set_defaults(func=cmd_harvest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand is None:
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except ToolkitError as exc:
        print(f"{RED}error:{RESET} {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(f"\n{YELLOW}interrupted.{RESET}", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
