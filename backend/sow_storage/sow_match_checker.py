# ─────────────────────────────────────────────
# 🔍 SOW COMBINED MATCH CHECKER (Postgres + FAISS)
# ─────────────────────────────────────────────
from sow_storage.sow_db_writer import check_sow_exists, is_duplicate, get_connection
from sow_storage.sow_faiss_store import check_existing_faiss_record
from sow_storage.sow_faiss_store import _build_texts


def check_combined_status(structured: dict, unstructured: dict) -> str:
    """
    Checks both PostgreSQL (structured) and FAISS (unstructured)
    at once and returns a single unified status.

    Returns:
      - "DUPLICATE"       → exists in both stores with identical content
      - "REVIEW_REQUIRED" → exists but content differs, or stores are out of sync
      - "NEW"             → not found in either store
    """

    sow_id       = structured.get("sow_id", "")
    reference_msa = structured.get("reference_msa", "")

    # ── Build unstructured text chunks (mirrors sow_faiss_store._build_texts) ──
    texts = _build_texts(unstructured, sow_id, reference_msa)

    # ── Check FAISS ────────────────────────────────────────────
    faiss_status = check_existing_faiss_record(sow_id, texts)

    # ── Check PostgreSQL ───────────────────────────────────────
    conn = get_connection()
    cur  = conn.cursor()

    try:
        exists = check_sow_exists(cur, sow_id)

        if exists:
            duplicate = is_duplicate(cur, sow_id, structured)
            pg_status = "DUPLICATE" if duplicate else "REVIEW_REQUIRED"
        else:
            pg_status = "NEW"

    finally:
        cur.close()
        conn.close()

    print(f"[CHECK] Postgres → {pg_status} | FAISS → {faiss_status}")

    # ── Combined decision ──────────────────────────────────────
    if pg_status == "DUPLICATE" and faiss_status == "DUPLICATE":
        return "DUPLICATE"

    if pg_status == "NEW" and faiss_status == "NEW":
        return "NEW"

    # Any mismatch or partial match (one store updated, other not) = review
    return "REVIEW_REQUIRED"