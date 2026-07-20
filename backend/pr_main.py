import logging
import os
import re
import sys

from PR_config.PR_settings import (
    RAW_TEXT_OUTPUT,
    OUTPUT_DIR
)

from PR_ocr.PR_pdf_to_image import pdf_to_images
from PR_ocr.PR_paddle_ocr import extract_text
from PR_ocr.PR_pdf_text_extractor import extract_text_from_pdf

from PR_processing.PR_pdf_detector import is_digital_pdf
from PR_processing.PR_rule_based_extractor import extract_with_rules

from PR_llm.PR_extractor import extract_fields

from PR_processing.PR_cleaner import clean_json
from PR_processing.PR_validator import validate

from PR_storage.PR_match_checker import check_combined_status

from PR_processing.PR_summary_generator import (
    generate_summary
)

from PR_storage.PR_postgres_writer import (
    save_to_postgres,
    save_summary_to_db,
    save_unstructured_to_db,
    deactivate_old_records
)

from PR_storage.PR_faiss_store import store_in_faiss


# ==================================================
# ENCODING FIX
# ==================================================
sys.stdout.reconfigure(
    encoding="utf-8",
    errors="replace"
)

sys.stderr.reconfigure(
    encoding="utf-8",
    errors="replace"
)

# ==================================================
# LOGGER
# ==================================================
logger = logging.getLogger("pr_main")


# ==================================================
# OCR TEXT CLEANUP
# ==================================================
def clean_ocr_text(text):

    if not text:
        return ""

    # Remove null chars
    text = text.replace("\x00", " ")

    # Normalize line breaks
    text = text.replace("\r", "\n")

    # Remove extra tabs
    text = text.replace("\t", " ")

    # Remove multiple spaces
    text = re.sub(r"[ ]{2,}", " ", text)

    # Remove multiple line breaks
    text = re.sub(r"\n{2,}", "\n", text)

    # Remove weird unicode noise
    text = re.sub(
        r"[^\x00-\x7F]+",
        " ",
        text
    )

    return text.strip()


# ==================================================
# SAVE RAW TEXT
# ==================================================
def save_raw_text(text):

    try:

        with open(
            RAW_TEXT_OUTPUT,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(text)

    except Exception as e:

        logger.warning(
            "Failed to save raw text: %s",
            str(e)
        )


# ==================================================
# MAIN PROCESS
# ==================================================
def process_file(file_path, file_id=None):

    """
    Process PR PDF file and extract structured
    and unstructured fields.
    """

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ==================================================
    # FILE VALIDATION
    # ==================================================
    if not os.path.exists(file_path):

        logger.error(
            "File not found: %s",
            file_path
        )

        return {
            "status": "failed",
            "reason": "file_not_found",
            "file_id": file_id
        }

    logger.info("Processing PR File: %s", file_path)

    logger.info("File ID: %s", file_id)

    # ==================================================
    # STEP 1: TEXT EXTRACTION
    # ==================================================
    try:

        if is_digital_pdf(file_path):

            logger.info("Digital PDF detected")

            text = extract_text_from_pdf(file_path)

        else:

            logger.info("Scanned PDF detected")

            logger.info("Running OCR...")

            images = pdf_to_images(file_path)

            text = extract_text(images)

    except Exception as e:

        logger.error(
            "Text extraction failed: %s",
            str(e)
        )

        return {
            "status": "failed",
            "reason": "text_extraction_failed",
            "file_id": file_id
        }

    # ==================================================
    # TEXT VALIDATION
    # ==================================================
    if not text:

        logger.error("No text extracted")

        return {
            "status": "failed",
            "reason": "no_text_extracted",
            "file_id": file_id
        }

    # ==================================================
    # STEP 2: OCR CLEANUP
    # ==================================================
    text = clean_ocr_text(text)

    logger.info(
        "OCR text cleaned successfully"
    )

    # Save raw text
    save_raw_text(text)

    logger.info(
        "Raw OCR text saved"
    )

    # ==================================================
    # STEP 3: RULE-BASED EXTRACTION
    # ==================================================
    try:

        rule_data = extract_with_rules(text)

        logger.info(
            "Rule extraction completed"
        )

        logger.info(
            "RULE DATA: %s",
            rule_data
        )

    except Exception as e:

        logger.error(
            "Rule extraction failed: %s",
            str(e)
        )

        rule_data = {}

    # ==================================================
    # STEP 4: PREPARE LLM INPUT
    # ==================================================
    short_text = text[:8000]

    # ==================================================
    # STEP 5: LLM EXTRACTION
    # ==================================================
    try:

        raw_response = extract_fields(
            short_text,
            rule_data
        )

        logger.info(
            "RAW LLM RESPONSE: %s",
            raw_response
        )

    except Exception as e:

        logger.error(
            "LLM extraction failed: %s",
            str(e)
        )

        return {
            "status": "failed",
            "reason": "llm_extraction_failed",
            "file_id": file_id
        }

    # ==================================================
    # STEP 6: CLEAN JSON
    # ==================================================
    try:

        data = clean_json(raw_response)

        logger.info(
            "CLEANED DATA: %s",
            data
        )

    except Exception as e:

        logger.error(
            "JSON cleaning failed: %s",
            str(e)
        )

        return {
            "status": "failed",
            "reason": "json_cleaning_failed",
            "file_id": file_id
        }

    # ==================================================
    # STEP 7: VALIDATE
    # ==================================================
    try:

        data = validate(data)

        logger.info(
            "VALIDATED DATA: %s",
            data
        )

    except Exception as e:

        logger.error(
            "Validation failed: %s",
            str(e)
        )

        return {
            "status": "failed",
            "reason": "validation_failed",
            "file_id": file_id
        }

    # ==================================================
    # STEP 8: SUMMARY
    # ==================================================
    try:

        summary = generate_summary(data)

        save_summary_to_db(
            summary,
            file_id
        )

        logger.info(
            "PR Summary generated and saved"
        )

    except Exception as e:

        logger.error(
            "Summary generation failed: %s",
            str(e)
        )

    # ==================================================
    # STEP 9: STRUCTURED DATA
    # ==================================================
    structured = data.get(
        "structured",
        {}
    )

    if not structured:

        logger.error(
            "No PR structured data found"
        )

        return {
            "status": "failed",
            "reason": "no_structured_data",
            "file_id": file_id
        }

    if not any(structured.values()):

        logger.error(
            "PR structured fields are empty"
        )

        return {
            "status": "failed",
            "reason": "structured_fields_empty",
            "file_id": file_id
        }

    structured["file_id"] = file_id

    # ==================================================
    # STEP 10: UNSTRUCTURED DATA
    # ==================================================
    unstructured = data.get(
        "unstructured",
        {}
    )

    # ==================================================
    # STEP 11: MATCH CHECK
    # ==================================================
    try:

        status = check_combined_status(
            structured,
            unstructured
        )

        logger.info(
            "FINAL MATCH STATUS: %s",
            status
        )

    except Exception as e:

        logger.error(
            "Match checking failed: %s",
            str(e)
        )

        status = "NEW"

    # ==================================================
    # STEP 12: DUPLICATE HANDLING
    # ==================================================
    if status == "DUPLICATE":

        logger.info(
            "Duplicate PR record detected"
        )

        logger.info(
            "Skipping insertion"
        )

        return {
            "status": "success",
            "match_status": "DUPLICATE",
            "file_id": file_id
        }

    elif status == "REVIEW_REQUIRED":

        logger.info(
            "Updated PR record detected"
        )

        logger.info(
            "Deactivating old PR records"
        )

        deactivate_old_records(
            structured
        )

        structured["active_flag"] = 1

    else:

        logger.info(
            "New PR record detected"
        )

        structured["active_flag"] = 1

    # ==================================================
    # STEP 13: SAVE STRUCTURED DATA → POSTGRES
    # ==================================================
    try:

        save_to_postgres(
            structured,
            file_id=file_id
        )

        logger.info(
            "PR structured data saved to Postgres"
        )

    except Exception as e:

        logger.error(
            "Postgres save failed: %s",
            str(e)
        )

    # ==================================================
    # STEP 14: SAVE UNSTRUCTURED DATA → FAISS
    # ==================================================
    try:

        pr_id = structured.get("pr_id")

        store_in_faiss(
            unstructured,
            pr_id=pr_id,
            status=status,
            file_id=file_id
        )

        logger.info(
            "PR unstructured data saved to FAISS"
        )

    except Exception as e:

        logger.error(
            "FAISS save failed: %s",
            str(e)
        )

    # ==================================================
    # STEP 15: SAVE UNSTRUCTURED DATA → POSTGRES
    # ==================================================
    try:

        save_unstructured_to_db(
            unstructured,
            file_id=file_id
        )

        logger.info(
            "PR unstructured data saved to Postgres"
        )

    except Exception as e:

        logger.error(
            "Unstructured Postgres save failed: %s",
            str(e)
        )

    # ==================================================
    # DONE
    # ==================================================
    logger.info("PR processing completed successfully")

    return {
        "status": "success",
        "match_status": status,
        "file_id": file_id
    }


# ==================================================
# MAIN
# ==================================================
def main():

    if len(sys.argv) < 2:

        print(
            "Usage: python pr_main.py <file_path> [file_id]"
        )

        return

    file_path = sys.argv[1]

    file_id = (
        int(sys.argv[2])
        if len(sys.argv) >= 3
        else None
    )

    process_file(
        file_path,
        file_id
    )


if __name__ == "__main__":
    main()