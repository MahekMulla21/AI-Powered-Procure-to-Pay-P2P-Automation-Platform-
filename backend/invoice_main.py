import logging
import os
import sys

from Invoice_config.Invoice_settings import OUTPUT_DIR
from Invoice_ocr.Invoice_pdf_to_image import pdf_to_images
from Invoice_ocr.Invoice_paddle_ocr import extract_text
from Invoice_ocr.Invoice_pdf_text_extractor import extract_text_from_pdf

from Invoice_processing.Invoice_pdf_detector import is_digital_pdf
from Invoice_processing.Invoice_rule_based_extractor import extract_with_rules

from Invoice_llm.Invoice_extractor import extract_fields
from Invoice_processing.Invoice_cleaner import clean_json
from Invoice_processing.Invoice_validator import validate

from Invoice_storage.Invoice_match_checker import check_combined_status
from Invoice_processing.Invoice_summary_generator import generate_summary
from Invoice_storage.Invoice_postgres_writer import (
    save_to_postgres,
    save_summary_to_db,
    deactivate_old_records,
    save_to_extracted_dataset
)
from Invoice_storage.Invoice_faiss_store import store_in_faiss

# Encoding fix
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Module-level logger ────────────────────────────────────────────────────────
# PipelineFilter on the root logger will auto-stamp [INVOICE] on every record
# emitted from this module while it runs in the INVOICE thread.
logger = logging.getLogger("invoice_main")


def process_file(file_path, file_id=None):
    """
    Process Invoice PDF file and extract structured data.

    Args:
        file_path (str): Path to PDF file
        file_id (int): File ID from files_dataset (for DB reference)
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return

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
        return

    # ===============================
    # STEP 2: RULE EXTRACTION
    # ===============================
    rule_data = extract_with_rules(text)
    logger.info("Rule-based extraction done: %s", rule_data)

    # ===============================
    # STEP 3: LLM
    # ===============================
    short_text = text
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
    logger.info("SUMMARY: %s", summary)

    # ===============================
    # STEP 7: STRUCTURED DATA
    # ===============================
    structured = data.get("structured", {})

    if not structured or not any(structured.values()):
        logger.error("No valid structured data")
        return

    structured["file_id"] = file_id

    # ===============================
    # STEP 7.5: COMBINED MATCH CHECK
    # ===============================
    unstructured = data.get("unstructured", {})
    status = check_combined_status(structured, unstructured)

    logger.info("[FINAL MATCH STATUS] -> %s", status)

    if status == "DUPLICATE":
        logger.info("Duplicate in both stores -> Skipping insert")
        return

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
    save_to_extracted_dataset(summary, file_id=file_id)

    # ===============================
    # STEP 9: SAVE UNSTRUCTURED -> FAISS
    # ===============================
    invoice_id = file_id

    store_in_faiss(
        unstructured=unstructured,
        invoice_number=structured.get("invoice_number"),
        invoice_id=invoice_id,
        status=status,
        file_id=file_id
    )
    logger.info("Done!")
    return {
        "status": "success",
        "file_id": file_id,
        "invoice_number": structured.get("invoice_number")
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python invoice_main.py <file_path> [file_id]")
        return

    file_path = sys.argv[1]
    file_id = int(sys.argv[2]) if len(sys.argv) >= 3 else None

    process_file(file_path, file_id)


if __name__ == "__main__":
    main()