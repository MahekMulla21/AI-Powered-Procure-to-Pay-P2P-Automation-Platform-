# ─────────────────────────────────────────────
# 🔍 COMBINED MATCH CHECKER (Postgres + FAISS)
# ─────────────────────────────────────────────
from Invoice_storage.Invoice_postgres_writer import check_existing_record
from Invoice_storage.Invoice_faiss_store import check_existing_faiss_record


def check_combined_status(structured: dict, unstructured: dict) -> str:
    """
    Checks both PostgreSQL (structured) and FAISS (unstructured)
    at once and returns a single unified status.

    Returns:
      - "DUPLICATE"       → exists in both with same content
      - "REVIEW_REQUIRED" → exists but content differs (or out of sync)
      - "NEW"             → not found in either
    """

    invoice_number = structured.get("invoice_number")

    # ── Build unstructured texts (same as store_in_faiss) ──
    texts = [
        f"Description of Service: {unstructured.get('description_of_service', '')}",
    ]

    # ── Check both stores ──────────────────────────────────
    pg_status    = check_existing_record(structured)
    faiss_status = check_existing_faiss_record(invoice_number, texts)

    print(f"[CHECK] Postgres → {pg_status} | FAISS → {faiss_status}")

    # ── Combined decision ──────────────────────────────────
    if pg_status == "DUPLICATE" and faiss_status == "DUPLICATE":
        return "DUPLICATE"

    if pg_status == "NEW" and faiss_status == "NEW":
        return "NEW"

    # Any mismatch or partial match = needs review
    return "REVIEW_REQUIRED"