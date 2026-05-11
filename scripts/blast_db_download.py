#!/usr/bin/env python3
"""Download and extract NCBI core_nt BLAST database volumes.

Fetches the metadata manifest, compares MD5 checksums against previously
downloaded files, and only downloads volumes that are new or changed.

Usage:
    Run from the target directory (e.g. /mnt/data/blastdbs/2026_03_06/):
        python3 blast_db_download.py
"""

import argparse
import json
import logging
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from urllib.request import urlopen

METADATA_URL = (
    "https://ftp.ncbi.nlm.nih.gov/blast/db/core_nt-nucl-metadata.json"
)
FTP_BASE_URL = "https://ftp.ncbi.nlm.nih.gov/blast/db"
CHECKSUM_DIR = Path("checksums")
MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 10  # seconds; doubles each attempt

# Skip chunks 00..(FROM_CHUNK - 1). Set to 0 to download all.
FROM_CHUNK = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)


def fetch_metadata() -> list[str]:
    """Return the list of volume filenames from the NCBI manifest."""
    log.info("Fetching metadata from %s", METADATA_URL)
    with urlopen(METADATA_URL) as resp:
        data = json.loads(resp.read())
    filenames = [url.rsplit("/", 1)[-1] for url in data["files"]]
    log.info("Manifest contains %d volumes", len(filenames))
    return filenames


def chunk_number(filename: str) -> int | None:
    """Extract chunk index from e.g. core_nt.42.tar.gz."""
    m = re.search(r"\.(\d+)\.tar\.gz$", filename)
    return int(m.group(1)) if m else None


def fetch_remote_md5(filename: str) -> str:
    """Download the .md5 file for a volume and return the checksum string."""
    url = f"{FTP_BASE_URL}/{filename}.md5"
    with urlopen(url) as resp:
        content = resp.read().decode().strip()
    # Format is typically "<md5>  <filename>" or just "<md5>"
    return content.split()[0]


def read_local_md5(filename: str) -> str | None:
    """Read a previously saved checksum, or None if not present."""
    path = CHECKSUM_DIR / f"{filename}.md5"
    if path.exists():
        return path.read_text().strip().split()[0]
    return None


def save_local_md5(filename: str, md5: str) -> None:
    """Persist a checksum for future comparison."""
    CHECKSUM_DIR.mkdir(exist_ok=True)
    path = CHECKSUM_DIR / f"{filename}.md5"
    path.write_text(f"{md5}  {filename}\n")


def download_tarball(filename: str) -> Path:
    """Download a .tar.gz volume with curl, retrying on failure.

    Uses curl's ``-C -`` flag to resume partial downloads so that
    retries do not re-fetch data that was already written to disk.
    """
    url = f"{FTP_BASE_URL}/{filename}"
    dest = Path(filename)
    for attempt in range(1, MAX_RETRIES + 1):
        log.info(
            "Downloading %s (attempt %d/%d)",
            url, attempt, MAX_RETRIES,
        )
        result = subprocess.run(
            ["curl", "-f", "-L", "-C", "-", "-o", str(dest), url],
        )
        if result.returncode == 0:
            return dest
        delay = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
        log.warning(
            "curl failed (exit %d) for %s — "
            "retrying in %ds",
            result.returncode, filename, delay,
        )
        time.sleep(delay)
    raise RuntimeError(
        f"Failed to download {filename} after {MAX_RETRIES} attempts"
    )


def extract_tarball(path: Path, keep: bool = False) -> float:
    """Extract a .tar.gz archive into the current directory.

    Returns the number of seconds spent extracting.
    """
    log.info("Extracting %s", path)
    t0 = time.monotonic()
    with tarfile.open(path, "r:gz") as tar:
        tar.extractall()
    elapsed = time.monotonic() - t0
    if keep:
        log.info("Kept %s (--keep)", path)
    else:
        path.unlink()
        log.info("Removed %s after extraction", path)
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and extract NCBI core_nt BLAST database volumes."
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep compressed .tar.gz files after extraction.",
    )
    args = parser.parse_args()

    filenames = fetch_metadata()

    to_download = []
    for fn in filenames:
        chunk = chunk_number(fn)
        if chunk is not None and chunk < FROM_CHUNK:
            continue

        remote_md5 = fetch_remote_md5(fn)
        local_md5 = read_local_md5(fn)

        if remote_md5 == local_md5:
            log.info("SKIP %s (checksum unchanged)", fn)
            continue

        to_download.append((fn, remote_md5))

    if not to_download:
        log.info("All volumes are up to date — nothing to download")
        return

    log.info("%d volume(s) to download", len(to_download))

    total_extract_secs = 0.0
    for fn, remote_md5 in to_download:
        tarball = download_tarball(fn)
        total_extract_secs += extract_tarball(tarball, keep=args.keep)
        save_local_md5(fn, remote_md5)
        log.info("DONE  %s", fn)

    log.info(
        "All downloads complete — %.1fs spent extracting",
        total_extract_secs,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
