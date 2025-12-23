from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from utils import (
    find_invalid_country_rows,
    save_upload_to_tempfile,
    run_p0_validation,
    parse_errors,
    fix_sample_id_spaces,
    find_taxa_zero_rows,
    find_invalid_pmi
)
import tempfile
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
    metadata_csv: UploadFile | None = File(None),
    query_fasta: UploadFile = File(...),
    metadata_text: str | None = Form(None)
):
    """
    Accepts uploaded metadata CSV and FASTA,
    runs validation, returns structured errors or success.
    """
    tmp_files = []
    try:
        # Use uploaded file or edited CSV
        if metadata_text:
            fd, metadata_path_str = tempfile.mkstemp(suffix='.csv')
            os.close(fd)
            metadata_path = Path(metadata_path_str)
            with metadata_path.open('w', encoding='utf-8') as f:
                f.write(metadata_text)
        elif metadata_csv:
            metadata_path = save_upload_to_tempfile(metadata_csv)
        else:
            return JSONResponse(status_code=400,
                                content={
                                    "ok": False,
                                    "error": "No metadata CSV provided"
                                    }
                                )
        tmp_files.append(metadata_path)

        query_path = save_upload_to_tempfile(query_fasta)
        tmp_files.append(query_path)

        rc, out, err = run_p0_validation(
            VALIDATION_SCRIPT,
            metadata_path,
            query_path,
            TAXONKIT_DB
            )
        if rc == 0:
            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()
            with open(query_path, "r", encoding="utf-8") as f:
                fasta_text = f.read()
            return {
                "ok": True,
                "message": "Validation passed",
                "metadata_csv": csv_text,
                "query_fasta": fasta_text
            }
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
                    "metadata_csv": csv_text,
                },
            )

        if parsed.get("type") == "metadata_missing_sample":
            bad_sample_id = parsed.get("sample_id")

            # if bad_sample_id and " " in bad_sample_id:
            if bad_sample_id:
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
                    with open(query_path, "r", encoding="utf-8") as f:
                        fasta_text = f.read()
                    return {
                        "ok": True,
                        "message": (
                            f'Validation passed. Auto-fixed sample_id: '
                            f'"{bad_sample_id}" → "{fixed_sample_id}"'
                        ),
                        "metadata_csv": csv_text,
                        "query_fasta": fasta_text
                    }

                parsed = parse_errors(err2)

        if parsed.get("type") == "invalid_taxa_of_interest":
            rows = find_taxa_zero_rows(metadata_path)
            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": parsed,
                    "rows": rows,
                    "metadata_csv": csv_text
                }
            )

        if parsed.get("type") == "invalid_pmi":
            rows = find_invalid_pmi(metadata_path)
            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": parsed,
                    "rows": rows,
                    "metadata_csv": csv_text,
                }
            )

        if parsed.get("type") == "invalid_country":
            rows = find_invalid_country_rows(
                metadata_path,
                parsed.get("value"))
            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": parsed,
                    "rows": rows,
                    "metadata_csv": csv_text,
                }
            )

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
