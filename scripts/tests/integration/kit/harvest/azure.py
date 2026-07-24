"""Single-blob Azure downloads for the harvest ``azure`` profile branch.

Blob URIs on Nextflow's Azure Batch profile look like
``az://<container>/<blob-path>``. We only ever fetch one file at a time
— never mirror the whole workdir — because task workdirs can be
multi-GB.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .errors import HarvestError

AZURE_URI_RE = re.compile(
    r"^az://(?P<container>[^/]+)/(?P<path>.+)$"
)


def azure_download(workdir_uri: str, filename: str, dest: Path) -> None:
    """Download a single blob individually — never mirror the workdir."""
    m = AZURE_URI_RE.match(workdir_uri)
    if not m:
        raise HarvestError(
            f"Malformed Azure work-dir URI: {workdir_uri}"
        )
    container = m.group("container")
    blob_path = f"{m.group('path').rstrip('/')}/{filename}"
    account = os.environ.get("STORAGE_ACCOUNT_STD", "daffstandard")
    key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
    if not key:
        raise HarvestError(
            "AZURE_STORAGE_ACCOUNT_KEY is not set."
            " Source deployment/azure/batch-helpers.sh and run az_load_env"
            " before harvesting from an Azure run."
        )
    cmd = [
        "az", "storage", "blob", "download",
        "--account-name", account,
        "--account-key", key,
        "--container-name", container,
        "--name", blob_path,
        "--file", str(dest),
        "--only-show-errors",
        "--no-progress",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        msg = (res.stderr or res.stdout).strip()
        raise HarvestError(
            f"az blob download failed for {container}/{blob_path}:\n"
            f"  {msg}"
        )
