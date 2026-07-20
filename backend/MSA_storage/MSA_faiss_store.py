import faiss
import numpy as np
import pickle
import os
from datetime import datetime
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#OUTPUT_DIR = os.path.join(BASE_DIR, "MSA_data", "output")

# backend/faiss_db/output
OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "faiss_db",
    "output"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

FAISS_INDEX_FILE = os.path.join(
    OUTPUT_DIR,
    "global_faiss.index"
)

FAISS_MAPPING_FILE = os.path.join(
    OUTPUT_DIR,
    "global_faiss_mapping.pkl"
)

print("FAISS OUTPUT DIR:", OUTPUT_DIR)

# ─────────────────────────────────────────────
# 📦 LOAD EXISTING FAISS INDEX + MAPPING
# ─────────────────────────────────────────────
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
    if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(FAISS_MAPPING_FILE):
        index = faiss.read_index(FAISS_INDEX_FILE)
        with open(FAISS_MAPPING_FILE, "rb") as f:
            mapping = pickle.load(f)
        return index, mapping
    return None, []

# ─────────────────────────────────────────────
# 🔍 CHECK EXISTING FAISS RECORD
# ─────────────────────────────────────────────
def check_existing_faiss_record(msa_id: str, new_texts: list[str]) -> str:
    """
    Checks only ACTIVE records (active_flag == 1).

    Returns:
      - "DUPLICATE"       → same msa_id AND same text content
      - "REVIEW_REQUIRED" → same msa_id but different text content (updated)
      - "NEW"             → msa_id not found in FAISS store
    """
    _, mapping = load_faiss_store()

    for entry in mapping:
        # ✅ Only check against active records
        if entry.get("msa_id") == msa_id and entry.get("active_flag", 1) == 1:
            if entry.get("texts") == new_texts:
                return "DUPLICATE"
            else:
                return "REVIEW_REQUIRED"

    return "NEW"


# ─────────────────────────────────────────────
# 🔥 DEACTIVATE OLD FAISS RECORDS (SCD Type 2)
# ─────────────────────────────────────────────
def deactivate_old_faiss_records(msa_id: str):
    """
    SCD Type 2: Instead of deleting old records, stamps end_timestamp
    and sets active_flag = 0 to close them. History is preserved in pkl.
    FAISS vector index is rebuilt using only active entries.
    """
    index, mapping = load_faiss_store()

    if not mapping:
        print("[INFO] No existing FAISS records to deactivate")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated = False

    # ── SCD Type 2: Close active records instead of removing ──
    for entry in mapping:
        if entry.get("msa_id") == msa_id and entry.get("active_flag", 1) == 1:
            entry["end_timestamp"] = now    # ← stamp closure time
            entry["active_flag"]   = 0      # ← mark as inactive
            updated = True

    if not updated:
        print(f"[INFO] No active FAISS records found for msa_id={msa_id}")
        return

    # ── Rebuild FAISS index from ACTIVE entries only ──
    active_entries = [e for e in mapping if e.get("active_flag", 1) == 1]

    if active_entries:
        all_texts  = [t for entry in active_entries for t in entry["texts"]]
        embeddings = model.encode(all_texts)
        dim        = embeddings.shape[1]
        new_index  = faiss.IndexFlatL2(dim)
        new_index.add(np.array(embeddings))
        faiss.write_index(new_index, FAISS_INDEX_FILE)
    else:
        # No active records left — write empty index
        dim         = model.get_sentence_embedding_dimension()
        empty_index = faiss.IndexFlatL2(dim)
        faiss.write_index(empty_index, FAISS_INDEX_FILE)

    # ── Persist full mapping (active + closed history) ──
    with open(FAISS_MAPPING_FILE, "wb") as f:
        pickle.dump(mapping, f)

    closed_count = len([e for e in mapping if e.get("msa_id") == msa_id and e.get("active_flag") == 0])
    print(f"[FAISS] SCD2: {closed_count} record(s) closed for msa_id={msa_id} | end_timestamp={now}")


# ─────────────────────────────────────────────
# 💾 STORE IN FAISS (SCD TYPE 2)
# ─────────────────────────────────────────────
def store_in_faiss(unstructured: dict, msa_id: str, status: str = None, file_id=None):
    texts = [
        f"Intellectual Property: {unstructured.get('intellectual_property', '')}",
        f"Dispute Resolution: {unstructured.get('dispute_resolution', '')}",
        f"Confidentiality: {unstructured.get('confidentiality', '')}",
        f"Liability: {unstructured.get('liability_clause', '')}",
        f"Indemnification: {unstructured.get('indemnification_clause', '')}",
    ]

    if status is None:
        print(f"[WARN] No status passed — running FAISS check independently")
        status = check_existing_faiss_record(msa_id, texts)

    if file_id:
        print(f"[FAISS] Processing for file_id={file_id} | msa_id={msa_id}")

    # ── Skip entirely if duplicate ────────────────
    if status == "DUPLICATE":
        print(f"[FAISS] Duplicate — skipping insert for msa_id={msa_id}")
        return status

    # ── SCD Type 2: Close old record before inserting new ──
    if status == "REVIEW_REQUIRED":
        print(f"[FAISS] Updated record — closing old vectors for msa_id={msa_id}")
        deactivate_old_faiss_records(msa_id)

    # ── Load existing store (post-deactivation if updated) ──
    index, mapping = load_faiss_store()

    # ── Encode and add new vectors ────────────────
    embeddings = model.encode(texts)
    dim        = embeddings.shape[1]

    if index is None:
        index = faiss.IndexFlatL2(dim)

    index.add(np.array(embeddings))

    # ── Append new mapping entry with SCD Type 2 timestamps ──
    mapping.append({
        "msa_id":          msa_id,
        "texts":           texts,
        "file_id":         file_id,
        "start_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # ← open new record
        "end_timestamp":   None,                                            # ← NULL = currently active
        "active_flag":     1                                                # ← mark as active
    })

    # ── Persist ───────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    faiss.write_index(index, FAISS_INDEX_FILE)

    with open(FAISS_MAPPING_FILE, "wb") as f:
        pickle.dump(mapping, f)

    print(f"[FAISS] Stored {len(texts)} vectors for msa_id={msa_id} | Status: {status} | start_timestamp: {mapping[-1]['start_timestamp']}")
    return status