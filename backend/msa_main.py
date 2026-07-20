import logging
import os
import sys

from MSA_config.MSA_settings import RAW_TEXT_OUTPUT, OUTPUT_DIR

from MSA_ocr.MSA_pdf_to_image import pdf_to_images
from MSA_ocr.MSA_paddle_ocr import extract_text
from MSA_ocr.MSA_pdf_text_extractor import extract_text_from_pdf

from MSA_processing.MSA_pdf_detector import is_digital_pdf
from MSA_processing.MSA_rule_based_extractor import extract_with_rules

from MSA_llm.MSA_extractor import extract_fields
from MSA_processing.MSA_cleaner import clean_json
from MSA_processing.MSA_validator import validate

from MSA_storage.MSA_match_checker import check_combined_status
from MSA_processing.MSA_summary_generator import generate_summary
from MSA_storage.MSA_postgres_writer import (
    save_to_postgres,
    save_summary_to_db,
    deactivate_old_records
)
from MSA_storage.MSA_faiss_store import store_in_faiss

# Encoding fix
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger("msa_main")


def process_file(file_path, file_id=None) -> dict:
    """
    Process MSA PDF file and extract structured data.

    Returns a dict with:
        match_status : "NEW" | "DUPLICATE" | "REVIEW_REQUIRED"
        doc_id       : primary key e.g. "MSA-TCS-STC-2024-001"
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return {"match_status": "ERROR", "doc_id": ""}

    logger.info("Processing: %s", file_path)
    logger.info("File ID: %s", file_id)

    # ===============================
    # STEP 1: TEXT EXTRACTION
    # ===============================
    if is_digital_pdf(file_path):
        logger.info("Digital PDF")
        text = extract_text_from_pdf(file_path)
    else:
        logger.info("OCR Running...")
        images = pdf_to_images(file_path)
        text = extract_text(images)

    if not text:
        logger.error("No text extracted")
        return {"match_status": "ERROR", "doc_id": ""}

    # ===============================
    # STEP 2: RULE EXTRACTION
    # ===============================
    rule_data = extract_with_rules(text)
    logger.info("Rule-based extraction done: %s", rule_data)

    # ===============================
    # STEP 3: LLM
    # ===============================
    short_text = text[:2500]
    raw_response = extract_fields(short_text, rule_data)
    logger.info("RAW LLM RESPONSE: %s", raw_response)

    # ===============================
    # STEP 4: CLEAN
    # ===============================
    data = clean_json(raw_response)
    logger.info("CLEANED DATA: %s", data)

    # ===============================
    # STEP 5: VALIDATE
    # ===============================
    data = validate(data)
    logger.info("VALIDATED DATA: %s", data)

    # ===============================
    # STEP 6: SUMMARY
    # ===============================
    summary = generate_summary(data)
    save_summary_to_db(summary, file_id)
    print("===== SUMMARY:", summary)
    logger.info("SUMMARY: %s", summary)

    # ===============================
    # STEP 7: STRUCTURED DATA
    # ===============================
    structured = data.get("structured", {})

    if not structured or not any(structured.values()):
        logger.error("No valid structured data")
        return {"match_status": "ERROR", "doc_id": ""}

    structured["file_id"] = file_id

    # ===============================
    # STEP 7.5: COMBINED MATCH CHECK
    # ===============================
    unstructured = data.get("unstructured", {})
    status = check_combined_status(structured, unstructured)

    logger.info("[FINAL MATCH STATUS] -> %s", status)

    msa_id = structured.get("msa_id", "")

    if status == "DUPLICATE":
        logger.info("Duplicate in both stores -> Skipping insert")
        return {"match_status": "DUPLICATE", "doc_id": msa_id}

    elif status == "REVIEW_REQUIRED":
        logger.info("Updated record -> Deactivating old records in both stores")
        deactivate_old_records(structured)
        structured["active_flag"] = 1

    else:
        logger.info("New record -> Inserting into both stores")
        structured["active_flag"] = 1

    # ===============================
    # STEP 8: SAVE STRUCTURED -> POSTGRES
    # ===============================
    save_to_postgres(structured, file_id=file_id)

    # ===============================
    # STEP 9: SAVE UNSTRUCTURED -> FAISS
    # ===============================
    store_in_faiss(unstructured, msa_id=msa_id, status=status, file_id=file_id)
    logger.info("Done!")

    return {"match_status": status, "doc_id": msa_id}


def main():
    if len(sys.argv) < 2:
        print("Usage: python msa_main.py <file_path> [file_id]")
        return

    file_path = sys.argv[1]
    file_id = int(sys.argv[2]) if len(sys.argv) >= 3 else None

    result = process_file(file_path, file_id)
    print(f"Result: {result}")


if __name__ == "__main__":
    main()