"""SSH/SCP helpers for remote-source harvests.

Each helper wraps ``subprocess.run`` with a small retry loop for
transient network failures, and raises :class:`HarvestError` with the
underlying stderr when all attempts fail.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from pathlib import Path
from typing import Callable, TypeVar

from .errors import HarvestError

DEFAULT_ATTEMPTS = 3
# Seconds between retries; len must be >= attempts-1.
DEFAULT_DELAYS = (1.0, 3.0)

T = TypeVar("T")


def _with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    delays: tuple[float, ...] = DEFAULT_DELAYS,
    label: str = "operation",
) -> T:
    """Call ``fn()`` up to ``attempts`` times, sleeping between failures."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except HarvestError as exc:
            last = exc
            if i == attempts - 1:
                break
            delay = delays[min(i, len(delays) - 1)]
            print(
                f"  {label} failed (attempt {i + 1}/{attempts});"
                f" retrying in {delay:.0f}s..."
            )
            time.sleep(delay)
    assert last is not None
    raise last


def remote_ls(host: str, path: Path) -> list[str]:
    """Return the basenames of entries directly under ``host:path``.

    An empty directory returns ``[]``. A missing path raises
    :class:`HarvestError` with ssh's stderr.
    """
    def _once() -> list[str]:
        cmd = ["ssh", host, f"ls -1 {shlex.quote(str(path))}"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            msg = (res.stderr or res.stdout).strip()
            raise HarvestError(
                f"ssh {host} ls {path} failed:\n  {msg}"
            )
        return [line for line in res.stdout.splitlines() if line]
    return _with_retries(_once, label=f"ssh {host} ls {path}")


def remote_fetch(host: str, path: Path, dest: Path) -> None:
    """Copy ``host:path`` to local ``dest`` via ``scp``.

    ``dest``'s parent directory must already exist.
    """
    def _once() -> None:
        cmd = [
            "scp", "-q", "-p",
            "-o", "BatchMode=yes",
            f"{host}:{path}", str(dest),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            msg = (res.stderr or res.stdout).strip()
            raise HarvestError(
                f"scp {host}:{path} failed:\n  {msg}"
            )
    _with_retries(_once, label=f"scp {host}:{path}")


def remote_readlink(host: str, path: Path) -> str | None:
    """Return the target of a remote symlink, or ``None`` if not a symlink."""
    def _once() -> str | None:
        cmd = ["ssh", host, f"readlink {shlex.quote(str(path))}"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            # readlink exits non-zero for non-symlinks; treat as "no target".
            return None
        text = res.stdout.strip()
        return text or None
    return _with_retries(_once, label=f"ssh {host} readlink {path}")


def remote_is_file(host: str, path: Path) -> bool:
    """Return True if ``host:path`` exists and is a regular file."""
    def _once() -> bool:
        cmd = ["ssh", host, f"test -f {shlex.quote(str(path))}"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0
    return _with_retries(_once, label=f"ssh {host} test -f {path}")
