# app.py
import os
import re
import tempfile
import traceback
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse

app = FastAPI()
HOST = "cloudgene.qcif.edu.au"
RX_GET = re.compile(
    r"https://cloudgene\.qcif\.edu\.au/get/([A-Za-z0-9_-]{10,})")
RX_URL = re.compile(
    r"https://cloudgene\.qcif\.edu\.au/share/results/[^\s\"']+")
RX_REPORT = re.compile(r"/report[^/\s]*\.html$", re.I)
INDEX_HTML = Path(__file__).parent / "index.html"


def extract_report_urls(input_text: str) -> list[str]:
    # If a get/<token> is present, fetch that script first
    m = RX_GET.search(input_text)
    if m:
        script_url = f"https://{HOST}/get/{m.group(1)}"
        r = requests.get(script_url, timeout=10)
        r.raise_for_status()
        text = r.text
    else:
        text = input_text

    urls = {u for u in RX_URL.findall(text) if RX_REPORT.search(u)}
    if not urls:
        raise HTTPException(400, "No report*.html URLs found.")
    if len(urls) > 1000:
        raise HTTPException(400, "Too many files requested.")
    return sorted(urls)


@app.get("/")
def download_page():
    """
    Serve the HTML page for downloading reports.
    """
    return HTMLResponse(content=INDEX_HTML.read_text(), status_code=200)


@app.post("/reports.zip")
def download_reports(payload: dict = Body(...)):
    print("Request received")
    raw = payload.get("input", "")
    if not raw:
        print("No input field, returning 400")
        raise HTTPException(400, "Missing 'input' field.")
    urls = extract_report_urls(raw)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    zip_path = tmp.name
    tmp.close()
    url = None
    try:
        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as zf:
            for url in urls:
                p = urlparse(url)
                if p.scheme != "https" or p.netloc != HOST:
                    print(f"Skipping invalid URL: {url}")
                    continue  # strict allow-list to avoid SSRF
                print(f"Fetching {url}")
                parent = os.path.basename(os.path.dirname(p.path))
                fname = os.path.basename(p.path)
                # keeps files distinct and meaningful
                arcname = f"{parent}_{fname}"
                with requests.get(url, stream=True, timeout=30) as r:
                    print(f"HTTP {r.status_code} for {url}")
                    r.raise_for_status()
                    print(f"Compressing response to {arcname}")
                    with zf.open(arcname, "w") as dest:
                        for chunk in r.iter_content(8192):
                            if chunk:
                                dest.write(chunk)
        print(f"Serving {zip_path}")
        return FileResponse(
            zip_path,
            filename="reports.zip",
            media_type="application/zip",
        )
    except Exception as e:
        print(f"Error bundling {url}: {e}\n{traceback.format_exc()}")
        raise HTTPException(502, f"Bundling failed for url {url}: {e}")
