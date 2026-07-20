# ─────────────────────────────────────────────
# 🔍 COMBINED MATCH CHECKER (Postgres + FAISS)
# ─────────────────────────────────────────────
from PO_storage.po_postgres_writer import check_existing_record
from PO_storage.po_faiss_store import check_existing_faiss_record


def check_combined_status(structured: dict, unstructured: dict) -> str:
    """
    Checks both PostgreSQL (structured) and FAISS (unstructured)
    at once and returns a single unified status.
    """
    po_id = structured.get("po_id")
    
    # Check PostgreSQL
    pg_status = check_existing_record(structured)
    
    # Check FAISS
    texts = unstructured.get("description_of_goods_and_services", "")
    if isinstance(texts, str):
        texts = [texts]
    faiss_status = check_existing_faiss_record(po_id, texts)

    print(f"[CHECK] Postgres → {pg_status} | FAISS → {faiss_status}")

    # ── Combined decision ──────────────────────────────────
    # ✅ FIX: Trust Postgres for structured data duplicate detection
    # If Postgres says DUPLICATE, it's a duplicate (even if FAISS differs on text)
    if pg_status == "DUPLICATE":
        return "DUPLICATE"
    
    # If both say NEW, it's definitely new
    if pg_status == "NEW" and faiss_status == "NEW":
        return "NEW"

    # Any other case = needs review (same po_id but different content)
    return "REVIEW_REQUIRED"