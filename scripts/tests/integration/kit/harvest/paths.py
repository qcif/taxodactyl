"""``RemotePath`` — argparse type that understands ``host:path`` sources.

``testkit.py`` accepts the run's ``.nextflow.log`` (and optionally
``--outdir`` / ``--trace`` / ``--work-dir``) as either a local path or a
``host:path`` SSH source. This module provides the small parser used as
``type=RemotePath`` in the argparse config.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ``host:path`` iff the string has a colon before any slash AND the head
# is an SSH-style host token. This avoids treating absolute paths or
# Windows-style ``C:\`` paths as remote.
_HOST_RE = re.compile(r"^(?P<host>[A-Za-z0-9._-]+):(?P<rest>.+)$")


@dataclass(frozen=True)
class RemotePath:
    """A path that may live on a remote host reachable via ``ssh``.

    ``remote`` is the SSH host or ``None`` for local paths. ``path`` is
    the filesystem path on that host (or on the local machine when
    ``remote`` is ``None``).
    """
    remote: str | None
    path: Path

    def __init__(self, raw: str):
        # ``argparse`` calls the type with the raw argument string, so
        # keep the constructor accepting a single string.
        m = _HOST_RE.match(raw)
        if m and "/" not in m.group("host"):
            object.__setattr__(self, "remote", m.group("host"))
            object.__setattr__(self, "path", Path(m.group("rest")))
        else:
            object.__setattr__(self, "remote", None)
            object.__setattr__(self, "path", Path(raw))

    def __str__(self) -> str:
        if self.remote is None:
            return str(self.path)
        return f"{self.remote}:{self.path}"

    @property
    def is_remote(self) -> bool:
        return self.remote is not None

    def with_host_from(self, other: "RemotePath") -> "RemotePath":
        """Inherit ``other``'s host if this path is local.

        Used so ``--log daff-admin:/…/nextflow.log --outdir /…/output``
        treats ``--outdir`` as remote on ``daff-admin`` without the user
        having to repeat the host.
        """
        if self.remote is not None or other.remote is None:
            return self
        inherited = RemotePath.__new__(RemotePath)
        object.__setattr__(inherited, "remote", other.remote)
        object.__setattr__(inherited, "path", self.path)
        return inherited

    def joinpath(self, *parts: str) -> "RemotePath":
        """Return a new RemotePath with additional path segments joined."""
        joined = RemotePath.__new__(RemotePath)
        object.__setattr__(joined, "remote", self.remote)
        object.__setattr__(joined, "path", self.path.joinpath(*parts))
        return joined
