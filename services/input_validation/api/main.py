from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from utils import (
    find_invalid_country_rows,
    find_invalid_locus_rows,
    save_upload_to_tempfile,
    run_p0_validation,
    parse_errors,
    find_taxa_zero_rows,
    find_invalid_pmi
)
import tempfile
import os
import logging

logger = logging.getLogger("taxon.validate")
logging.basicConfig(
    level=logging.INFO,  # change to DEBUG when debugging
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


app = FastAPI(title="Taxodactyl input validation API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def parsed_error_to_dict(err):
    return {
        "type": err.type,
        "message": err.message,
        "sample_id": err.sample_id,
        "value": err.value,
    }


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
    logger.info("Validation request received")
    tmp_files = []

    try:
        # Use uploaded file or edited CSV
        if metadata_text:
            fd, metadata_path_str = tempfile.mkstemp(suffix='.csv')
            os.close(fd)
            metadata_path = Path(metadata_path_str)
            with metadata_path.open('w', encoding='utf-8') as f:
                f.write(metadata_text)
            logger.info("Metadata CSV created from edited text")
        elif metadata_csv:
            metadata_path = save_upload_to_tempfile(metadata_csv)
            logger.info("Metadata CSV uploaded: %s", metadata_csv.filename)
        else:
            logger.warning("No metadata CSV provided")
            return JSONResponse(status_code=400,
                                content={
                                    "ok": False,
                                    "error": "No metadata CSV provided"
                                    }
                                )
        tmp_files.append(metadata_path)

        query_path = save_upload_to_tempfile(query_fasta)
        tmp_files.append(query_path)
        logger.info(
            "Files prepared | metadata=%s | fasta=%s",
            metadata_path.name,
            query_path.name,
        )

        logger.info("Running p0 validation")
        result = run_p0_validation(
            metadata_path,
            query_path
            )
        logger.info("p0 validation finished | rc=%s", result.ok)
        if result.ok:
            logger.info("Validation passed successfully")
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
        parsed = parse_errors(result.error or "")
        logger.warning(
            "Validation failed | type=%s | message=%s",
            parsed.type,
            parsed.message,
        )

        if parsed.type == "invalid_taxa_of_interest":
            rows = find_taxa_zero_rows(metadata_path)
            logger.warning(
                "Invalid taxa_of_interest detected | rows=%s",
                rows,
            )
            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": parsed_error_to_dict(parsed),
                    "rows": rows,
                    "metadata_csv": csv_text
                }
            )

        if parsed.type == "invalid_pmi":
            rows = find_invalid_pmi(metadata_path)
            logger.warning(
                "Invalid PMI detected | rows=%s",
                rows,
            )
            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": parsed_error_to_dict(parsed),
                    "rows": rows,
                    "metadata_csv": csv_text,
                }
            )

        if parsed.type == "invalid_country":
            rows = find_invalid_country_rows(
                metadata_path,
                parsed.value)
            logger.warning(
                "Invalid country detected | value=%s | rows=%s",
                parsed.value,
                rows,
            )
            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": parsed_error_to_dict(parsed),
                    "rows": rows,
                    "metadata_csv": csv_text,
                }
            )

        if parsed.type == "invalid_required_columns":
            logger.warning(
                "Missing required CSV columns | columns=%s",
                parsed.value,
            )

            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()

            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": parsed_error_to_dict(parsed),
                    "invalid_columns": parsed.value,
                    "metadata_csv": csv_text,
                }
            )

        if parsed.type == "invalid_locus":
            rows = find_invalid_locus_rows(
                metadata_path,
                parsed.value
            )
            logger.warning(
                "Invalid locus detected | value=%s | rows=%s",
                parsed.value,
                rows,
            )

            with open(metadata_path, "r", encoding="utf-8") as f:
                csv_text = f.read()

            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": parsed_error_to_dict(parsed),
                    "rows": rows,
                    # "column": "preliminary_id",
                    "metadata_csv": csv_text,
                }
            )

        with open(metadata_path, 'r', encoding='utf-8') as f:
            csv_text = f.read()

        logger.error("Unhandled validation error | %s", parsed)
        return JSONResponse(status_code=400, content={
            "ok": False,
            "error": parsed_error_to_dict(parsed),
            "metadata_csv": csv_text})

    finally:
        # cleanup temp files
        for p in tmp_files:
            try:
                os.remove(p)
                logger.debug("Temp file removed: %s", p)
            except Exception:
                pass
