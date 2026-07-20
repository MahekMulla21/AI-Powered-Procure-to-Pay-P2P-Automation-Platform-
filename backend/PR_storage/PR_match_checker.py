# ─────────────────────────────────────────────
# 🔍 COMBINED MATCH CHECKER (Postgres + FAISS)
# ─────────────────────────────────────────────
from PR_storage.PR_postgres_writer import check_existing_record
from PR_storage.PR_faiss_store import check_existing_faiss_record


def check_combined_status(structured: dict, unstructured: dict) -> str:
    """
    Checks both PostgreSQL (structured) and FAISS (unstructured)
    at once and returns a single unified status.

    Returns:
      - "DUPLICATE"       → exists in both with same content
      - "REVIEW_REQUIRED" → exists but content differs (or out of sync)
      - "NEW"             → not found in either
    """

    pr_id = structured.get("pr_id")

    # ===============================
    # BUILD UNSTRUCTURED TEXTS
    # (same format as store_in_faiss)
    # ===============================
    quantity = unstructured.get("quantity", {})

    if isinstance(quantity, dict):
        quantity_str = ", ".join(
            f"{k}: {v}" for k, v in quantity.items()
        ) if quantity else "NA"
    else:
        quantity_str = str(quantity) if quantity else "NA"

    texts = [
        f"Quantity: {quantity_str}",
        f"Location: {unstructured.get('location', '') or 'NA'}",
        f"Description: {unstructured.get('description', '') or 'NA'}",
    ]

    print(f"[CHECK] PR ID      → {pr_id}")
    print(f"[CHECK] Texts      → {texts}")

    # ===============================
    # CHECK BOTH STORES
    # ===============================
    pg_status    = check_existing_record(structured)
    faiss_status = check_existing_faiss_record(pr_id, texts)

    print(f"[CHECK] Postgres   → {pg_status}")
    print(f"[CHECK] FAISS      → {faiss_status}")

    # ===============================
    # COMBINED DECISION
    # ===============================
    if pg_status == "DUPLICATE" and faiss_status == "DUPLICATE":
        return "DUPLICATE"

    if pg_status == "NEW" and faiss_status == "NEW":
        return "NEW"

    # Any mismatch or partial match = needs review
    return "REVIEW_REQUIRED"