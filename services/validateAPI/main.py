from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from utils import (
    save_upload_to_tempfile,
    run_p0_validation,
    parse_errors,
    fix_sample_id_spaces,
    find_taxa_zero_rows)
import tempfile
# import shutil
import os
from dotenv import load_dotenv
load_dotenv()


app = FastAPI(title="TAXON p0 validator API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_SCRIPT = REPO_ROOT / 'scripts' / 'p0_validation.py'
TAXONKIT_DB = os.getenv("TAXONKIT_DB")
if not TAXONKIT_DB:
    raise RuntimeError("TAXONKIT_DB environment variable not set")

TAXONKIT_DB = Path(TAXONKIT_DB)
if not TAXONKIT_DB.exists():
    raise RuntimeError(f"TAXONKIT_DB does not exist: {TAXONKIT_DB}")


@app.post('/validate')
async def validate(
    metadata_csv: UploadFile = File(...),
    query_fasta: UploadFile = File(...),
    taxdb_dir: str | None = Form(None)
):
    """
    Accepts uploaded metadata CSV and FASTA,
    runs validation, returns structured errors or success.
    """
    tmp_files = []
    try:
        metadata_path = save_upload_to_tempfile(metadata_csv)
        query_path = save_upload_to_tempfile(query_fasta)
        tmp_files.extend([metadata_path, query_path])
        # taxdb_path = Path(taxdb_dir) if taxdb_dir else None

        rc, out, err = run_p0_validation(
            VALIDATION_SCRIPT,
            metadata_path,
            query_path,
            TAXONKIT_DB
            # taxdb_path
            )
        if rc == 0:
            return {"ok": True, "message": "Validation passed"}
        parsed = parse_errors(err)

        if parsed.get("type") == "taxa_zero":
            rows = find_taxa_zero_rows(metadata_path)

            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()

            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "type": "taxa_zero",
                        "message": (
                            "Invalid value '0' found in "
                            "taxa_of_interest column"
                        ),
                    },
                    "rows": rows,
                    "metadata_csv": csv_text,  # ✅ REQUIRED for editor
                },
            )

        if parsed.get("type") == "metadata_missing_sample":
            bad_sample_id = parsed.get("sample_id")

            if bad_sample_id and " " in bad_sample_id:
                fixed_sample_id = fix_sample_id_spaces(
                    metadata_path,
                    query_path,
                    bad_sample_id
                )

                # re-run validation after auto-fix
                rc2, out2, err2 = run_p0_validation(
                    VALIDATION_SCRIPT,
                    metadata_path,
                    query_path,
                    TAXONKIT_DB
                )

                if rc2 == 0:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        csv_text = f.read()

                    return {
                        "ok": True,
                        "message": (
                            f'Validation passed. Auto-fixed sample_id: '
                            f'"{bad_sample_id}" → "{fixed_sample_id}"'
                        ),
                        "metadata_csv": csv_text
                    }

                # still failing → return new parsed error
                parsed = parse_errors(err2)

        with open(metadata_path, 'r', encoding='utf-8') as f:
            csv_text = f.read()
        return JSONResponse(status_code=400, content={
            "ok": False,
            "error": parsed,
            "metadata_csv": csv_text})

    finally:
        # cleanup temp files
        for p in tmp_files:
            try:
                os.remove(p)
            except Exception:
                pass


@app.post('/revalidate')
async def revalidate(
    metadata_text: str = Form(...),
    query_fasta: UploadFile = File(...),
    # taxdb_dir: str | None = Form(None)
):
    """
    Accepts edited metadata CSV text and original FASTA (or reupload),
    writes temp csv and re-runs validation."""
    tmp_files = []
    try:
        fd, metadata_path = tempfile.mkstemp(suffix='.csv')
        os.close(fd)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            f.write(metadata_text)
        tmp_files.append(metadata_path)

        query_path = save_upload_to_tempfile(query_fasta)
        tmp_files.append(query_path)

        # taxdb_path = Path(taxdb_dir) if taxdb_dir else None
        rc, out, err = run_p0_validation(
            VALIDATION_SCRIPT,
            Path(metadata_path),
            query_path,
            TAXONKIT_DB
            # taxdb_path
            )
        if rc == 0:
            return {"ok": True, "message": "Validation passed"}
        parsed = parse_errors(err)
        return JSONResponse(status_code=400, content={
            "ok": False,
            "error": parsed})
    finally:
        for p in tmp_files:
            try:
                os.remove(p)
            except Exception:
                pass


@app.get('/health')
def health():
    return {"ok": True}
