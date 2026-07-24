"""Copy a single required file out of a task workdir into a case dir.

Three transports are supported:

- **local** — direct filesystem read (with stale-symlink remap when a
  ``--work-dir`` override is given).
- **azure** — single-blob ``az storage blob download`` per file.
- **remote** — ``scp host:<workdir>/<file>`` per file. Optional
  ``remote_host`` is passed in when the run's workdirs live on an SSH
  host.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .azure import azure_download
from .errors import HarvestError
from .remote import remote_fetch, remote_readlink, remote_is_file

# Some older workflow versions publish task outputs under ``output/``
# rather than at workdir root (Cloudgene's v1.4.4 runs do this).
CANDIDATE_SUBPATHS = ("", "output")


def _remap_local_workdir(
    workdir_uri: str,
    work_dir_override: Path | None,
) -> Path:
    """Return the local path to a task workdir, applying override if set.

    The override strips the log's stale workdir prefix and rebases onto
    ``work_dir_override``, matching by the trailing two path segments
    (``<hash-prefix>/<hash-tail>``) which uniquely identify a task.
    """
    p = Path(workdir_uri)
    if work_dir_override is None:
        return p
    if len(p.parts) < 2:
        raise HarvestError(
            f"Cannot remap workdir without at least two path segments:"
            f" {workdir_uri}"
        )
    tail = Path(*p.parts[-2:])
    return work_dir_override / tail


def _resolve_stale_symlink(
    src: Path, work_dir_override: Path,
) -> Path | None:
    """Remap a stale Nextflow staging symlink onto ``work_dir_override``.

    Nextflow stages inputs into each task workdir as symlinks to the
    producing task's workdir. When a run is copied off its original
    machine those symlink targets go stale. If the target's last three
    segments are ``<hash-prefix>/<hash-tail>/<filename>`` we can rebase
    them onto the override.
    """
    if not src.is_symlink():
        return None
    target = Path(os.readlink(src))
    if len(target.parts) < 3:
        return None
    rebased = work_dir_override / Path(*target.parts[-3:])
    return rebased if rebased.is_file() else None


def _materialise_local(
    workdir_uri: str,
    filename: str,
    dest: Path,
    work_dir_override: Path | None,
) -> None:
    base = _remap_local_workdir(workdir_uri, work_dir_override)
    for sub in CANDIDATE_SUBPATHS:
        src = base / sub / filename if sub else base / filename
        if src.is_file():
            shutil.copy2(src, dest)
            return
        if work_dir_override is not None:
            rebased = _resolve_stale_symlink(src, work_dir_override)
            if rebased is not None:
                shutil.copy2(rebased, dest)
                return
    tried = ", ".join(
        str(base / sub / filename if sub else base / filename)
        for sub in CANDIDATE_SUBPATHS
    )
    raise HarvestError(
        f"Expected file missing under local workdir (tried: {tried})"
    )


def _materialise_azure(
    workdir_uri: str,
    filename: str,
    dest: Path,
) -> None:
    last_err: HarvestError | None = None
    for sub in CANDIDATE_SUBPATHS:
        blob_name = f"{sub}/{filename}" if sub else filename
        try:
            azure_download(workdir_uri, blob_name, dest)
            return
        except HarvestError as exc:
            last_err = exc
    assert last_err is not None
    raise last_err


def _materialise_remote(
    host: str,
    workdir_uri: str,
    filename: str,
    dest: Path,
    work_dir_override_path: Path | None,
) -> None:
    """SCP a single file out of a remote task workdir."""
    base = Path(workdir_uri)
    if work_dir_override_path is not None and len(base.parts) >= 2:
        base = work_dir_override_path / Path(*base.parts[-2:])
    last_err: HarvestError | None = None
    for sub in CANDIDATE_SUBPATHS:
        remote_path = base / sub / filename if sub else base / filename
        try:
            if remote_is_file(host, remote_path):
                remote_fetch(host, remote_path, dest)
                return
            # If not a regular file, it might be a stale symlink pointing
            # at another task's workdir. Try readlink -> rebase.
            if work_dir_override_path is not None:
                target = remote_readlink(host, remote_path)
                if target:
                    target_path = Path(target)
                    if len(target_path.parts) >= 3:
                        rebased = (
                            work_dir_override_path
                            / Path(*target_path.parts[-3:])
                        )
                        if remote_is_file(host, rebased):
                            remote_fetch(host, rebased, dest)
                            return
        except HarvestError as exc:
            last_err = exc
    if last_err is not None:
        raise last_err
    tried = ", ".join(
        str(base / sub / filename if sub else base / filename)
        for sub in CANDIDATE_SUBPATHS
    )
    raise HarvestError(
        f"Expected file missing on {host} (tried: {tried})"
    )


def _try_outdir_fallback(
    outdir_local: Path | None,
    outdir_remote_host: str | None,
    outdir_remote_path: Path | None,
    subpath: str,
    dest: Path,
) -> bool:
    """Try to grab ``<outdir>/<subpath>`` (published file). Return success."""
    if outdir_remote_host is not None and outdir_remote_path is not None:
        candidate = outdir_remote_path / subpath
        try:
            if remote_is_file(outdir_remote_host, candidate):
                remote_fetch(outdir_remote_host, candidate, dest)
                return True
        except HarvestError:
            return False
        return False
    if outdir_local is not None:
        candidate = outdir_local / subpath
        if candidate.is_file():
            shutil.copy2(candidate, dest)
            return True
    return False


def materialise(
    workdir_uri: str,
    filename: str,
    dest: Path,
    *,
    is_azure: bool,
    remote_host: str | None = None,
    work_dir_override: Path | None = None,
    work_dir_override_remote: str | None = None,
    outdir_subpath: str | None = None,
    outdir_local: Path | None = None,
    outdir_remote_host: str | None = None,
    outdir_remote_path: Path | None = None,
) -> None:
    """Copy a single required file out of a task workdir into ``dest``.

    Tries ``<workdir>/<filename>`` first, then
    ``<workdir>/output/<filename>``. If both fail and ``outdir_subpath``
    is given, falls back to ``<outdir>/<outdir_subpath>`` — useful when
    the workdir is unreachable (stale staging symlinks, cleaned scratch)
    but the workflow published the file.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if is_azure:
        try:
            _materialise_azure(workdir_uri, filename, dest)
            return
        except HarvestError:
            if outdir_subpath and _try_outdir_fallback(
                outdir_local, outdir_remote_host, outdir_remote_path,
                outdir_subpath, dest,
            ):
                return
            raise
    if remote_host is not None:
        try:
            _materialise_remote(
                remote_host, workdir_uri, filename, dest,
                work_dir_override_path=(
                    work_dir_override
                    if work_dir_override_remote == remote_host
                    else None
                ),
            )
            return
        except HarvestError:
            if outdir_subpath and _try_outdir_fallback(
                outdir_local, outdir_remote_host, outdir_remote_path,
                outdir_subpath, dest,
            ):
                return
            raise
    try:
        _materialise_local(workdir_uri, filename, dest, work_dir_override)
    except HarvestError:
        if outdir_subpath and _try_outdir_fallback(
            outdir_local, outdir_remote_host, outdir_remote_path,
            outdir_subpath, dest,
        ):
            return
        raise
