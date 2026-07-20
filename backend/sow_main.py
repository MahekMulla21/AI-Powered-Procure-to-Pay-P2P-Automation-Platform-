import logging
import os
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger("sow_main")

_processing_lock = threading.Lock()

from sow_config import OUTPUT_DIR
from sow_ocr.sow_pdf_detector import is_digital_pdf
from sow_ocr.sow_pdf_text_extractor import extract_text_from_pdf
from sow_ocr.sow_pdf_to_image import pdf_to_images
from sow_ocr.sow_paddle_ocr import extract_text
from sow_processing.sow_structured import extract_structured, _detect_currency
from sow_processing.sow_unstructured import extract_unstructured
from sow_processing.sow_llm import enrich_with_llm, check_ollama_connection
from sow_storage.sow_db_writer import save_to_postgres, deactivate_old_sow, get_connection
from sow_storage.sow_faiss_store import store_in_faiss
from sow_storage.sow_match_checker import check_combined_status
from sow_ocr.sow_docx_extractor import extract_text_from_docx


def _clean_field(raw: str) -> str:
    if not raw:
        return raw
    raw = raw.split("|")[0].strip()
    tokens = str(raw).split()
    real = next(
        (t for t in tokens if "-" in t and any(c.isdigit() for c in t)),
        tokens[0] if tokens else raw
    )
    return real.strip()


def _clean_status_field(raw: str) -> str:
    if not raw:
        return "Active"
    known = ["Active", "Inactive", "Closed", "Draft", "Expired", "Completed"]
    for s in known:
        if s.lower() in str(raw).lower():
            return s
    return "Active"


def _clean_all_fields(data: dict) -> dict:
    for field in ["sow_id", "reference_msa", "vendor_id"]:
        if data.get(field):
            original = data[field]
            data[field] = _clean_field(data[field])
            if data[field] != original:
                logger.info("  [CLEAN] %s: '%s' -> '%s'", field, original, data[field])
    raw_status = str(data.get("status", "")).strip()
    data["status"] = _clean_status_field(raw_status)
    logger.info("  [CLEAN] status -> '%s'", data["status"])
    return data


def process_file(file_path: str, file_id=None) -> dict:
    """
    Entry point called by the backend/frontend upload handler.
    Acquires a global lock so multiple simultaneous uploads are
    processed sequentially.

    Returns a dict with:
        match_status : "NEW" | "DUPLICATE" | "REVIEW_REQUIRED"
        doc_id       : sow_id e.g. "SOW-TCS-STC-DM-2024-001"
    """
    logger.info("[QUEUE] Waiting for processing slot: %s", os.path.basename(file_path))
    with _processing_lock:
        return _process_file_impl(file_path, file_id)


def _process_file_impl(file_path: str, file_id=None) -> dict:

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(file_path):
        logger.error("File not found -> %s", file_path)
        return {"match_status": "ERROR", "doc_id": ""}

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".pdf", ".docx"):
        logger.error("Unsupported file type '%s'. Only PDF and DOCX supported.", ext)
        return {"match_status": "ERROR", "doc_id": ""}

    logger.info("=" * 60)
    logger.info("SOW EXTRACTION PIPELINE  v4 + Ollama LLM + FAISS")
    logger.info("File: %s", os.path.basename(file_path))
    logger.info("=" * 60)

    # ── STEP 1: TEXT EXTRACTION ───────────────────────────────
    logger.info("[STEP 1] Extracting text from document...")
    text = ""

    if ext == ".docx":
        logger.info("  Word document detected")
        text = extract_text_from_docx(file_path)
    elif is_digital_pdf(file_path):
        logger.info("  Digital PDF detected")
        text = extract_text_from_pdf(file_path)
    else:
        logger.info("  Scanned PDF — Running OCR")
        images = pdf_to_images(file_path)
        text = extract_text(images)

    if not text or not text.strip():
        logger.error("No text extracted")
        return {"match_status": "ERROR", "doc_id": ""}

    logger.info("  %d paragraphs, %d chars extracted", text.count("\n"), len(text))

    # ── STEP 2: RULE-BASED STRUCTURED FIELDS ─────────────────
    logger.info("[STEP 2] Extracting structured fields (rule-based)...")
    s_data, s_conf = extract_structured(text)
    s_found = sum(1 for v in s_data.values() if v)
    for f, v in s_data.items():
        tag = "OK" if v else "--"
        logger.info("  [%s] %-22s %s", tag, f, str(v)[:55] if v else "not found")

    # ── STEP 3: RULE-BASED UNSTRUCTURED FIELDS ───────────────
    logger.info("[STEP 3] Extracting unstructured fields (rule-based)...")
    currency = _detect_currency(text)
    u_data, u_conf = extract_unstructured(text, currency)
    u_found = sum(1 for v in u_data.values() if v)
    for f, v in u_data.items():
        tag   = "FOUND    " if v else "NOT FOUND"
        chars = f"({len(v)} chars)" if v else ""
        logger.info("  [%s] %-26s %s", tag, f, chars)

    total = len(s_data) + len(u_data)
    found = s_found + u_found
    rate  = round(found / total * 100, 1) if total else 0
    logger.info("  Rule-based Extraction Rate: %d/%d fields (%s%%)", found, total, rate)

    # ── STEP 4: OLLAMA LLM ENRICHMENT ────────────────────────
    logger.info("[STEP 4] Enriching with Ollama LLM (llama3)...")
    ollama_ok = check_ollama_connection()

    if ollama_ok:
        s_data, u_data = enrich_with_llm(text, s_data, u_data)
        llm_found = sum(1 for v in {**s_data, **u_data}.values() if v)
        llm_rate  = round(llm_found / total * 100, 1) if total else 0
        logger.info("  After LLM Enrichment Rate: %d/%d fields (%s%%)", llm_found, total, llm_rate)
    else:
        logger.warning("  Ollama not reachable — using rule-based data only.")

    # ── STEP 4.5: CLEAN FIELDS ────────────────────────────────
    logger.info("[STEP 4.5] Cleaning extracted fields...")
    all_data = {**s_data, **u_data}
    all_data = _clean_all_fields(all_data)

    if not all_data.get("sow_id"):
        all_data["sow_id"] = os.path.splitext(os.path.basename(file_path))[0][:50]
        logger.warning("  sow_id not found — using filename: %s", all_data["sow_id"])

    sow_id = all_data.get("sow_id", "")

    # ── STEP 5: COMBINED MATCH CHECK ─────────────────────────
    logger.info("[STEP 5] Running combined match check (Postgres + FAISS)...")
    status = check_combined_status(s_data, u_data)
    logger.info("  [FINAL STATUS] -> %s", status)

    if status == "DUPLICATE":
        logger.info("  File REJECTED — identical record exists in both stores.")
        logger.info("  DONE (DUPLICATE — no changes made)")
        return {"match_status": "DUPLICATE", "doc_id": sow_id}

    elif status == "REVIEW_REQUIRED":
        logger.info("  Updated SOW detected — deactivating old Postgres record...")
        conn = get_connection()
        cur  = conn.cursor()
        try:
            deactivate_old_sow(cur, sow_id)
            conn.commit()
        finally:
            cur.close()
            conn.close()
        all_data["active_flag"] = 1

    else:
        logger.info("  New SOW — will insert fresh records into both stores.")
        all_data["active_flag"] = 1

    # ── STEP 6: SAVE STRUCTURED -> POSTGRES ───────────────────
    logger.info("[STEP 6] Saving structured data to PostgreSQL...")
    try:
        result = save_to_postgres(all_data, file_id, pre_status=status)
        action = result.get("action", "UNKNOWN")
        logger.info("  DB ACTION : %s | sow_id: %s", action, result.get("sow_id", "?"))
    except Exception as e:
        logger.error("  DB error: %s", e)
        return {"match_status": "ERROR", "doc_id": sow_id}

    # ── STEP 7: SAVE UNSTRUCTURED -> FAISS ────────────────────
    logger.info("[STEP 7] Saving unstructured data to FAISS...")
    try:
        reference_msa = all_data.get("reference_msa", "")
        store_in_faiss(
            unstructured  = u_data,
            sow_id        = sow_id,
            reference_msa = reference_msa,
            status        = status,
        )
    except Exception as e:
        logger.error("  FAISS error: %s", e)

    logger.info("=" * 60)
    logger.info("DONE")
    logger.info("=" * 60)

    return {"match_status": status, "doc_id": sow_id}


def main():
    if len(sys.argv) < 2:
        print("\nUsage: python sow_main.py <pdf_path> [file_id]")
        return
    file_path = sys.argv[1]
    file_id   = int(sys.argv[2]) if len(sys.argv) >= 3 else None
    result = process_file(file_path, file_id)
    print(f"Result: {result}")


if __name__ == "__main__":
    main()