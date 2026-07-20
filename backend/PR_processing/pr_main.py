import os
import sys

from PR_config.PR_settings import RAW_TEXT_OUTPUT, OUTPUT_DIR

from PR_ocr.PR_pdf_to_image import pdf_to_images
from PR_ocr.PR_paddle_ocr import extract_text
from PR_ocr.PR_pdf_text_extractor import extract_text_from_pdf

from PR_processing.PR_pdf_detector import is_digital_pdf
from PR_processing.PR_rule_based_extractor import extract_with_rules

from PR_llm.PR_extractor import extract_fields
from PR_processing.PR_cleaner import clean_json
from PR_processing.PR_validator import validate

from PR_storage.PR_match_checker import check_combined_status
from PR_processing.PR_summary_generator import generate_summary
from PR_storage.PR_postgres_writer import (
    save_to_postgres,
    save_summary_to_db,
    deactivate_old_records
)
from PR_storage.PR_faiss_store import store_in_faiss

# Encoding fix
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def process_file(file_path, file_id=None):
    """
    Process PR PDF file and extract structured data.

    Args:
        file_path (str): Path to PDF file
        file_id (int): File ID from files_dataset (for DB reference)
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(file_path):
        print(" File not found")
        return

    print(f"\n Processing: {file_path}")
    print(f"[DEBUG] File ID: {file_id}")

    # ===============================
    # STEP 1: TEXT EXTRACTION
    # ===============================
    if is_digital_pdf(file_path):
        print(" Digital PDF")
        text = extract_text_from_pdf(file_path)
    else:
        print(" OCR Running...")
        images = pdf_to_images(file_path)
        text = extract_text(images)

    if not text:
        print(" No text extracted")
        return

    # ===============================
    # STEP 2: RULE EXTRACTION
    # ===============================
    rule_data = extract_with_rules(text)
    print('Rule-based extraction done.', rule_data)

    # ===============================
    # STEP 3: LLM
    # ===============================
    short_text = text[:2500]
    raw_response = extract_fields(short_text, rule_data)
    print("\n🔍 RAW LLM RESPONSE:\n")
    print(raw_response)

    # ===============================
    # STEP 4: CLEAN
    # ===============================
    data = clean_json(raw_response)
    print("\n🧹 CLEANED DATA:\n", data)

    # ===============================
    # STEP 5: VALIDATE
    # ===============================
    data = validate(data)
    print("\n✅ VALIDATED DATA:\n", data)

    # ===============================
    # STEP 6: SUMMARY
    # ===============================
    summary = generate_summary(data)
    save_summary_to_db(summary, file_id)
    print("\n📝 SUMMARY:\n", summary)

    # ===============================
    # STEP 7: STRUCTURED DATA
    # ===============================
    structured = data.get("structured", {})

    if not structured or not any(structured.values()):
        print(" No valid structured data")
        return

    # Include file_id in structured data
    structured["file_id"] = file_id

    # ===============================
    # 🔍 STEP 7.5: COMBINED MATCH CHECK
    # ===============================
    unstructured = data.get("unstructured", {})
    status = check_combined_status(structured, unstructured)

    print(f"[FINAL MATCH STATUS] → {status}")

    if status == "DUPLICATE":
        print("Duplicate in both stores → Skipping insert")
        return

    elif status == "REVIEW_REQUIRED":
        print("Updated record → Deactivating old records in both stores")
        deactivate_old_records(structured)
        structured["active_flag"] = 1

    else:
        print("New record → Inserting into both stores")
        structured["active_flag"] = 1

    # ===============================
    # STEP 8: SAVE STRUCTURED → POSTGRES
    # ===============================
    save_to_postgres(structured, file_id=file_id)

    # ===============================
    # STEP 9: SAVE UNSTRUCTURED → FAISS
    # ===============================
    pr_id = structured.get("pr_id")
    store_in_faiss(unstructured, pr_id=pr_id, status=status, file_id=file_id)
    print("\n✅ Done!")


def main():
    if len(sys.argv) < 2:
        print("Usage: python pr_main.py <file_path> [file_id]")
        return

    file_path = sys.argv[1]
    file_id = int(sys.argv[2]) if len(sys.argv) >= 3 else None

    process_file(file_path, file_id)


if __name__ == "__main__":
    main()