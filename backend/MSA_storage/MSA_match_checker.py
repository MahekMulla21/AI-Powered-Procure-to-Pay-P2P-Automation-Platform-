# ─────────────────────────────────────────────
# 🔍 COMBINED MATCH CHECKER (Postgres + FAISS)
# ─────────────────────────────────────────────
from MSA_storage.MSA_postgres_writer import check_existing_record
from MSA_storage.MSA_faiss_store import check_existing_faiss_record


def check_combined_status(structured: dict, unstructured: dict) -> str:
    """
    Checks both PostgreSQL (structured) and FAISS (unstructured)
    at once and returns a single unified status.

    Returns:
      - "DUPLICATE"       → exists in both with same content
      - "REVIEW_REQUIRED" → exists but content differs (or out of sync)
      - "NEW"             → not found in either
    """

    msa_id = structured.get("msa_id")

    # ── Build unstructured texts (same as store_in_faiss) ──
    texts = [
        f"Intellectual Property: {unstructured.get('intellectual_property', '')}",
        f"Dispute Resolution: {unstructured.get('dispute_resolution', '')}",
        f"Confidentiality: {unstructured.get('confidentiality', '')}",
        f"Liability: {unstructured.get('liability_clause', '')}",
        f"Indemnification: {unstructured.get('indemnification_clause', '')}",
    ]

    # ── Check both stores ──────────────────────
    pg_status   = check_existing_record(structured)
    faiss_status = check_existing_faiss_record(msa_id, texts)

    print(f"[CHECK] Postgres → {pg_status} | FAISS → {faiss_status}")

    # ── Combined decision ──────────────────────
    if pg_status == "DUPLICATE" and faiss_status == "DUPLICATE":
        return "DUPLICATE"

    if pg_status == "NEW" and faiss_status == "NEW":
        return "NEW"

    # Any mismatch or partial match = needs review
    return "REVIEW_REQUIRED"