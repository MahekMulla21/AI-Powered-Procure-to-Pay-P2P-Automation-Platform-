import faiss
import numpy as np
import pickle
import os
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "faiss_db", "output")
FAISS_INDEX_FILE = os.path.join(OUTPUT_DIR,"global_faiss.index")
FAISS_MAPPING_FILE = os.path.join(
    OUTPUT_DIR,
    "global_faiss_mapping.pkl"
)


# ─────────────────────────────────────────────
# 📦 LOAD EXISTING FAISS INDEX + MAPPING
# ─────────────────────────────────────────────
# def load_faiss_store():
#     """Returns (index, mapping) or (None, []) if not found."""
#     if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(FAISS_MAPPING_FILE):
#         index = faiss.read_index(FAISS_INDEX_FILE)
#         with open(FAISS_MAPPING_FILE, "rb") as f:
#             mapping = pickle.load(f)  # List of dicts: [{invoice_number, texts}, ...]
#         return index, mapping
#     return None, []

def load_faiss_store():
    """

    Returns:
        (index, mapping)

    mapping format:
    [
        {
            "doc_type": "SOW" | "PR" | "MSA" | "PO" | "Invoice",
            "doc_id": "...",
            "texts": [...],
            "metadata": {...},
            "start_timestamp": "...",
            "end_timestamp": None,
            "active_flag": 1
        }
    ]
    """
    print(f"[DEBUG FAISS LOAD] Checking files:")
    print(f"[DEBUG FAISS LOAD] Index path: {FAISS_INDEX_FILE}")
    print(f"[DEBUG FAISS LOAD] Mapping path: {FAISS_MAPPING_FILE}")
    print(f"[DEBUG FAISS LOAD] Index exists: {os.path.exists(FAISS_INDEX_FILE)}")
    print(f"[DEBUG FAISS LOAD] Mapping exists: {os.path.exists(FAISS_MAPPING_FILE)}")
    if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(FAISS_MAPPING_FILE):
        index = faiss.read_index(FAISS_INDEX_FILE)
        with open(FAISS_MAPPING_FILE, "rb") as f:
            mapping = pickle.load(f)
        return index, mapping
    return None, []

# ─────────────────────────────────────────────
# 🔍 CHECK EXISTING FAISS RECORD
# ─────────────────────────────────────────────
def check_existing_faiss_record(invoice_number: str, new_texts: list[str]) -> str:
    """
    Returns:
      - "DUPLICATE"       → same invoice_number AND same text content
      - "REVIEW_REQUIRED" → same invoice_number but different text content (updated)
      - "NEW"             → invoice_number not found in FAISS store
    """
    _, mapping = load_faiss_store()

    for entry in mapping:
        if entry.get("invoice_number") == invoice_number:
            if entry.get("texts") == new_texts:
                return "DUPLICATE"
            else:
                return "REVIEW_REQUIRED"

    return "NEW"


# ─────────────────────────────────────────────
# 🔥 DEACTIVATE (REMOVE) OLD FAISS RECORDS
# ─────────────────────────────────────────────
def deactivate_old_faiss_records(invoice_number: str):
    """
    Stamps old Invoice records as inactive (active_flag=0) for the given invoice_number.
    Rebuilds index using ONLY active records (active_flag=1) of ALL document types.
    """
    index, mapping = load_faiss_store()

    if not mapping:
        return

    updated = False
    for entry in mapping:
        if entry.get("doc_type") == "Invoice" and entry.get("invoice_number") == invoice_number and entry.get("active_flag", 1) == 1:
            entry["active_flag"] = 0
            updated = True

    if not updated:
        return

    # Rebuild index from all ACTIVE entries (Invoices, MSA, SOW, etc.)
    active_entries = [e for e in mapping if e.get("active_flag", 1) == 1]

    if active_entries:
        all_texts = [entry.get("text", "") for entry in active_entries]
        embeddings = model.encode(all_texts)
        dim = embeddings.shape[1]
        new_index = faiss.IndexFlatL2(dim)
        new_index.add(np.array(embeddings))
        faiss.write_index(new_index, FAISS_INDEX_FILE)
    else:
        dim = model.get_sentence_embedding_dimension()
        faiss.write_index(faiss.IndexFlatL2(dim), FAISS_INDEX_FILE)

    with open(FAISS_MAPPING_FILE, "wb") as f:
        pickle.dump(mapping, f)

    print(f"[FAISS] Deactivated old Invoice records for {invoice_number}")


# ─────────────────────────────────────────────
# 💾 STORE IN FAISS (WITH DUPLICATE LOGIC)
# ─────────────────────────────────────────────

def store_in_faiss(
    unstructured: dict,
    invoice_number: str,
    invoice_id=None,
    status: str = None,
    file_id=None
):
    texts = [
        f"Description of Service: {unstructured.get('description_of_service', '')}",
    ]

    if status is None:
        print(f"[WARN] No status passed — running FAISS check independently")
        status = check_existing_faiss_record(invoice_number, texts)

    if file_id:
        print(f"[FAISS] Processing for file_id={file_id} | invoice_number={invoice_number}")

    # ✅ Use passed status — no re-check needed
    if status == "DUPLICATE":
        print(f"[FAISS] Duplicate — skipping insert for invoice_number={invoice_number}")
        return status

    if status == "REVIEW_REQUIRED":
        print(f"[FAISS] Updated record — replacing old vectors for invoice_number={invoice_number}")
        deactivate_old_faiss_records(invoice_number)

    # ── Load existing store (post-deactivation if updated) ──
    index, mapping = load_faiss_store()

    # ── Encode and add new vectors ──────────────────────────
    embeddings = model.encode(texts)
    dim = embeddings.shape[1]

    if index is None:
        index = faiss.IndexFlatL2(dim)

    index.add(np.array(embeddings))

    # ── Update mapping (1 entry per vector for 1:1 RAG) ─────
    for text in texts:
        mapping.append({
            "doc_id":         invoice_number,
            "invoice_number": invoice_number,
            "text":           text,
            "doc_type":       "Invoice",
            "file_id":        file_id,
            "active_flag":    1
        })

    # ── Persist ─────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    faiss.write_index(index, FAISS_INDEX_FILE)

    with open(FAISS_MAPPING_FILE, "wb") as f:
        pickle.dump(mapping, f)

    print(f"[FAISS] Stored {len(texts)} vector(s) for invoice_number={invoice_number} | Status: {status}")
    return status