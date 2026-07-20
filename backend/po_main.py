import os
import sys
import re

# Add backend directory to Python path for module imports
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Normal imports using proper venv
from PO_config.po_settings import OUTPUT_DIR


def normalize_po_id(po_id):
    """
    Normalize po_id while preserving original structure.
    """

    if not po_id or str(po_id).strip() == "":
        return None

    po_id = str(po_id).strip().upper()

    # Replace spaces and underscores with hyphens
    po_id = re.sub(r'[\s_]+', '-', po_id)

    # Remove duplicate hyphens
    po_id = re.sub(r'-+', '-', po_id)

    return po_id


def _smart_text_slice(text: str, max_chars: int = 4000) -> str:
    """
    Build a smarter text slice for the LLM that includes both the document
    header section (PO metadata) AND the line-items table section.
    """

    header = text[:1500]

    table_start_kw = [
        'LINE ITEMS',
        'DESCRIPTION OF GOODS',
        'SERVICE ITEMS',
        'ITEMS & PRICES',
        'ITEM DETAILS',
        'SCHEDULE OF SERVICES'
    ]

    table_section = ''

    for kw in table_start_kw:

        idx = text.upper().find(kw)

        if idx != -1:

            start = max(0, idx - 100)

            table_section = text[start:start + 2500]

            break

    if table_section:

        combined = header + "\n\n[...]\n\n" + table_section

        return combined[:max_chars]

    return text[:max_chars]


from PO_ocr.po_pdf_to_image import pdf_to_images
from PO_ocr.po_paddle_ocr import extract_text
from PO_ocr.po_pdf_text_extractor import extract_text_from_pdf

from PO_processing.po_pdf_detector import is_digital_pdf
from PO_processing.po_rule_based_extractor import extract_with_rules

from PO_llm.po_extractor import extract_fields

from PO_processing.po_cleaner import clean_json
from PO_processing.po_validator import validate
from PO_processing.po_data_validator import validate_structured_data

from PO_processing.po_regularize_data import regularize_po_data

from PO_storage.po_match_checker import check_combined_status

from PO_storage.po_postgres_writer import (
    save_to_postgres,
    deactivate_old_po
)

from PO_storage.po_faiss_store import store_in_faiss


# ============================================================
# ENCODING FIX
# ============================================================

sys.stdout.reconfigure(
    encoding="utf-8",
    errors="replace"
)

sys.stderr.reconfigure(
    encoding="utf-8",
    errors="replace"
)


# ============================================================
# RULE-BASED PRIORITY FIELDS
# ============================================================

_ALWAYS_RULE_BASED_FIELDS = {

    "quantity",
    "unit_price",
    "tax",
    "service_code"
}


# ============================================================
# MAIN PROCESS FUNCTION
# ============================================================

def process_file(file_path, file_id=None):

    """
    Process PO file.
    """

    # ============================================================
    # STEP 0: OUTPUT DIRECTORY
    # ============================================================

    try:

        os.makedirs(
            OUTPUT_DIR,
            exist_ok=True
        )

    except Exception as e:

        print(
            f"[ERROR] Failed to create output directory: {e}"
        )

        return {
            "status": "failed",
            "message": str(e)
        }

    # ============================================================
    # STEP 0b: FILE VALIDATION
    # ============================================================

    if not file_path or not os.path.exists(file_path):

        print("[ERROR] File not found")

        return {
            "status": "failed",
            "message": "File not found"
        }

    print(f"\n[INFO] Processing: {file_path}")
    print(f"[DEBUG] File ID: {file_id}")

    text = None

    # ============================================================
    # STEP 1: TEXT EXTRACTION
    # ============================================================

    try:

        if is_digital_pdf(file_path):

            print("[INFO] Digital PDF detected")

            text = extract_text_from_pdf(file_path)

        else:

            print("[INFO] OCR Running...")

            images = pdf_to_images(file_path)

            if not images:

                print("[ERROR] No images extracted from PDF")

                return {
                    "status": "failed",
                    "message": "No images extracted"
                }

            text = extract_text(images)

        if not text:

            print("[ERROR] No text extracted")

            return {
                "status": "failed",
                "message": "No text extracted"
            }

    except Exception as e:

        print(f"[ERROR] Text extraction failed: {e}")

        return {
            "status": "failed",
            "message": str(e)
        }

    # ============================================================
    # STEP 2: LLM EXTRACTION
    # ============================================================

    llm_data = {}

    try:

        print("[INFO] Running LLM extraction...")

        smart_text = _smart_text_slice(
            text,
            max_chars=4000
        )

        raw_response = extract_fields(
            smart_text,
            {}
        )

        print("\n[DEBUG] RAW LLM RESPONSE:")
        print(raw_response)

        llm_data = clean_json(raw_response)

        print("[INFO] LLM extraction completed")

    except Exception as e:

        print(f"[WARN] LLM extraction failed: {e}")

        llm_data = {
            "structured": {},
            "unstructured": {}
        }

    # ============================================================
    # STEP 3: RULE-BASED EXTRACTION
    # ============================================================

    rule_data = {}

    try:

        rule_data = extract_with_rules(text)

        print("[INFO] Rule-based extraction completed")

    except Exception as e:

        print(f"[ERROR] Rule-based extraction failed: {e}")

        rule_data = {}

    # ============================================================
    # STEP 4: MERGE DATA
    # ============================================================

    merged_structured = {}
    merged_unstructured = {}

    # ------------------------------------------------------------
    # LLM DATA FIRST
    # ------------------------------------------------------------

    if llm_data:

        llm_structured = llm_data.get(
            "structured",
            {}
        )

        llm_unstructured = llm_data.get(
            "unstructured",
            {}
        )

        for field, value in llm_structured.items():

            if (
                value
                and field not in _ALWAYS_RULE_BASED_FIELDS
            ):

                merged_structured[field] = value

        for field, value in llm_unstructured.items():

            if value:
                merged_unstructured[field] = value

    # ------------------------------------------------------------
    # RULE-BASED DATA
    # ------------------------------------------------------------

    if rule_data:

        structured_fields = [

            "po_id",
            "po_date",
            "vendor_name",
            "client_name",
            "payment_terms",
            "delivery_terms",
            "currency",
            "total_amount",
            "start_date",
            "end_date",
            "reference_sow",
            "reference_msa",
            "quantity",
            "unit_price",
            "tax",
            "tax_breakup",
            "service_code",
            "delivery_location",
            "grn_indicator",
            "po_status"
        ]

        for field in structured_fields:

            if field in _ALWAYS_RULE_BASED_FIELDS:

                if (
                    field in rule_data
                    and rule_data[field]
                ):

                    merged_structured[field] = rule_data[field]

            else:

                if (
                    field in rule_data
                    and rule_data[field]
                ):

                    if (
                        field not in merged_structured
                        or not merged_structured[field]
                    ):

                        merged_structured[field] = rule_data[field]

        if "description_of_goods_and_services" in rule_data:

            if (
                "description_of_goods_and_services"
                not in merged_unstructured
                or not merged_unstructured[
                    "description_of_goods_and_services"
                ]
            ):

                merged_unstructured[
                    "description_of_goods_and_services"
                ] = rule_data[
                    "description_of_goods_and_services"
                ]

    # ============================================================
    # STEP 5: REGULARIZATION
    # ============================================================

    try:

        print("[INFO] Regularizing data...")

        merged_structured = regularize_po_data(
            text,
            merged_structured
        )

        print("[INFO] Regularization completed")

    except Exception as e:

        print(f"[WARN] Regularization failed: {e}")

    # ============================================================
    # STEP 6: NORMALIZE po_id
    # ============================================================

    if (
        "po_id" in merged_structured
        and merged_structured["po_id"]
    ):

        original_po_id = merged_structured["po_id"]

        normalized_po_id = normalize_po_id(
            original_po_id
        )

        if normalized_po_id != original_po_id:

            print(
                f"[INFO] Normalized po_id: "
                f"{original_po_id} → {normalized_po_id}"
            )

            merged_structured["po_id"] = normalized_po_id

    # ============================================================
    # STEP 7: BUILD DATA OBJECT
    # ============================================================

    data = {

        "structured": merged_structured,
        "unstructured": merged_unstructured
    }

    print(f"\n[INFO] Final merged data:\n{data}")

    # ============================================================
    # STEP 8: VALIDATION
    # ============================================================

    try:

        (
            is_valid,
            cleaned_structured,
            validation_errors
        ) = validate_structured_data(
            merged_structured
        )

        if validation_errors:

            print("\n[WARN] Validation errors:")

            for error in validation_errors:
                print(f"  - {error}")

        data["structured"] = cleaned_structured

        if is_valid:

            print("[INFO] Validation passed")

        else:

            print("[WARN] Validation issues found")

    except Exception as e:

        print(f"[ERROR] Validation layer failed: {e}")

    # ============================================================
    # STEP 9: LEGACY VALIDATOR
    # ============================================================

    try:

        data = validate(data)

        print("[INFO] Existing validator passed")

    except Exception as e:

        print(f"[ERROR] Existing validator failed: {e}")

    # ============================================================
    # STEP 10: STRUCTURED DATA
    # ============================================================

    structured = data.get("structured", {})

    unstructured = data.get("unstructured", {})

    if not structured or not any(structured.values()):

        print("[WARN] No structured data extracted")

        return {
            "status": "failed",
            "message": "No structured data extracted"
        }

    structured["file_id"] = file_id

    # ============================================================
    # STEP 11: MATCH CHECK
    # ============================================================

    status = "NEW"

    try:

        status = check_combined_status(
            structured,
            unstructured
        )

        print(f"[INFO] Match status: {status}")

    except Exception as e:

        print(f"[WARN] Match check failed: {e}")

        status = "NEW"

    # ------------------------------------------------------------
    # DUPLICATE
    # ------------------------------------------------------------

    if status == "DUPLICATE":

        print("[INFO] Duplicate found")

        return {
            "status": "duplicate",
            "structured": structured
        }

    # ------------------------------------------------------------
    # REVIEW REQUIRED
    # ------------------------------------------------------------

    elif status == "REVIEW_REQUIRED":

        print("[INFO] Updating existing PO")

        try:

            deactivate_old_po(
                structured.get("po_id")
            )

        except Exception as e:

            print(
                f"[ERROR] Failed to deactivate old PO: {e}"
            )

    else:

        print("[INFO] New PO detected")

    # ============================================================
    # STEP 12: SAVE TO POSTGRES
    # ============================================================

    try:

        save_to_postgres(
            structured,
            unstructured=unstructured,
            file_id=file_id
        )

        print("[INFO] Data saved to PostgreSQL")

    except Exception as e:

        print(f"[ERROR] PostgreSQL save failed: {e}")

    # ============================================================
    # STEP 13: SAVE TO FAISS
    # ============================================================

    try:

        store_in_faiss(
            unstructured,
            po_id=structured.get("po_id"),
            vendor_name=structured.get("vendor_name"),
            status=status,
            file_id=file_id
        )

        print("[INFO] Data saved to FAISS")

    except Exception as e:

        print(f"[ERROR] FAISS save failed: {e}")

    # ============================================================
    # SUCCESS
    # ============================================================

    print("\n[SUCCESS] PO processing completed!")

    return {

        "status": "success",
        "structured": structured,
        "unstructured": unstructured
    }


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) < 2:

        print(
            "Usage: python po_main.py "
            "<file_path> [file_id]"
        )

        return

    file_path = sys.argv[1]

    file_id = (
        int(sys.argv[2])
        if len(sys.argv) >= 3
        else None
    )

    result = process_file(
        file_path,
        file_id
    )

    print("\n========== FINAL RESULT ==========")
    print(result)


if __name__ == "__main__":
    main()