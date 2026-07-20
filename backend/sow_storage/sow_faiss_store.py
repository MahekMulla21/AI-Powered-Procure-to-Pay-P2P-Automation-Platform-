import faiss
import numpy as np
import pickle
import os
from datetime import datetime
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#OUTPUT_DIR = os.path.join(BASE_DIR, "sow_data", "output")
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
# def load_faiss_store():
#     """Returns (index, mapping) or (None, []) if not found."""
#     if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(FAISS_MAPPING_FILE):
#         index = faiss.read_index(FAISS_INDEX_FILE)
#         with open(FAISS_MAPPING_FILE, "rb") as f:
#             mapping = pickle.load(f)   # List of dicts: [{sow_id, reference_msa, texts, start_timestamp, end_timestamp, active_flag}, ...]
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
    if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(FAISS_MAPPING_FILE):
        index = faiss.read_index(FAISS_INDEX_FILE)
        with open(FAISS_MAPPING_FILE, "rb") as f:
            mapping = pickle.load(f)
        return index, mapping
    return None, []

# ─────────────────────────────────────────────
# 🔍 CHECK EXISTING FAISS RECORD
# ─────────────────────────────────────────────
def check_existing_faiss_record(sow_id: str, new_texts: list[str]) -> str:
    """
    Checks only ACTIVE records (active_flag == 1).

    Returns:
      - "DUPLICATE"       → same sow_id AND same text content
      - "REVIEW_REQUIRED" → same sow_id but different text content (updated SOW)
      - "NEW"             → sow_id not found in FAISS store
    """
    _, mapping = load_faiss_store()

    for entry in mapping:
        # ✅ Only check against active records
        if entry.get("sow_id") == sow_id and entry.get("active_flag", 1) == 1:
            if entry.get("texts") == new_texts:
                return "DUPLICATE"
            else:
                return "REVIEW_REQUIRED"

    return "NEW"


# ─────────────────────────────────────────────
# 🔥 DEACTIVATE OLD FAISS RECORDS (SCD Type 2)
# ─────────────────────────────────────────────
def deactivate_old_faiss_records(sow_id: str):
    """
    SCD Type 2: Instead of deleting old records, stamps end_timestamp
    and sets active_flag = 0 to close them. History is preserved in pkl.
    FAISS vector index is rebuilt using only active entries.
    """
    index, mapping = load_faiss_store()

    if not mapping:
        print("[INFO] No existing FAISS records to deactivate.")
        return

    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated = False

    # ── SCD Type 2: Close active records instead of removing ──
    for entry in mapping:
        if entry.get("sow_id") == sow_id and entry.get("active_flag", 1) == 1:
            entry["end_timestamp"] = now    # ← stamp closure time
            entry["active_flag"]   = 0      # ← mark as inactive
            updated = True

    if not updated:
        print(f"[INFO] No active FAISS records found for sow_id={sow_id}")
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

    closed_count = len([e for e in mapping if e.get("sow_id") == sow_id and e.get("active_flag") == 0])
    print(f"[FAISS] SCD2: {closed_count} record(s) closed for sow_id={sow_id} | end_timestamp={now}")


# ─────────────────────────────────────────────
# 🏗️  BUILD TEXT CHUNKS FROM SOW UNSTRUCTURED
# ─────────────────────────────────────────────
def _build_texts(unstructured: dict, sow_id: str, reference_msa: str) -> list[str]:
    """
    Converts SOW unstructured fields into labelled text chunks for embedding.
    Add / remove fields here to match your sow_unstructured extractor output.
    """
    return [
        f"SOW ID: {sow_id}",
        f"Reference MSA: {reference_msa}",
        f"Scope of Work: {unstructured.get('scope_of_work', '')}",
        f"Deliverables: {unstructured.get('deliverables', '')}",
        f"Payment Terms: {unstructured.get('payment_terms', '')}",
        f"Milestones: {unstructured.get('milestones', '')}",
        f"Penalty Clause: {unstructured.get('penalty_clause', '')}",
        f"Termination Clause: {unstructured.get('termination_clause', '')}",
        f"Confidentiality: {unstructured.get('confidentiality', '')}",
        f"Intellectual Property: {unstructured.get('intellectual_property', '')}",
        f"Liability: {unstructured.get('liability_clause', '')}",
        f"Indemnification: {unstructured.get('indemnification_clause', '')}",
        f"Dispute Resolution: {unstructured.get('dispute_resolution', '')}",
        f"Governing Law: {unstructured.get('governing_law', '')}",
        f"Amendments: {unstructured.get('amendments', '')}",
    ]


# ─────────────────────────────────────────────
# 💾 STORE SOW IN FAISS (SCD TYPE 2)
# ─────────────────────────────────────────────
def store_in_faiss(unstructured: dict, sow_id: str,
                   reference_msa: str = "", status: str = None) -> str:
    """
    Embeds and stores SOW unstructured fields in FAISS with SCD Type 2 tracking.

    Args:
        unstructured  : dict of unstructured SOW fields from sow_unstructured extractor
        sow_id        : unique SOW identifier
        reference_msa : linked MSA ID (stored in mapping for cross-reference)
        status        : pass pre-computed status to avoid a double FAISS check;
                        if None the check is run here.

    Returns:
        status string → "NEW" | "REVIEW_REQUIRED" | "DUPLICATE"
    """
    texts = _build_texts(unstructured, sow_id, reference_msa)

    # ── Determine status ──────────────────────────────────────
    if status is None:
        print(f"[WARN] No status passed — running FAISS check independently.")
        status = check_existing_faiss_record(sow_id, texts)

    # ── Duplicate → skip ──────────────────────────────────────
    if status == "DUPLICATE":
        print(f"[FAISS] Duplicate — skipping insert for sow_id={sow_id}")
        return status

    # ── SCD Type 2: Close old record before inserting new ─────
    if status == "REVIEW_REQUIRED":
        print(f"[FAISS] Updated SOW — closing old vectors for sow_id={sow_id}")
        deactivate_old_faiss_records(sow_id)

    # ── Load store (post-deactivation if updated) ─────────────
    index, mapping = load_faiss_store()

    # ── Encode new vectors ────────────────────────────────────
    embeddings = model.encode(texts)
    dim        = embeddings.shape[1]

    if index is None:
        index = faiss.IndexFlatL2(dim)

    index.add(np.array(embeddings))

    # ── Append new mapping entry with SCD Type 2 timestamps ──
    mapping.append({
        "sow_id"        : sow_id,
        "reference_msa" : reference_msa,
        "texts"         : texts,
        "start_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # ← open new record
        "end_timestamp"  : None,                                            # ← NULL = currently active
        "active_flag"    : 1                                                # ← mark as active
    })

    # ── Persist ───────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    faiss.write_index(index, FAISS_INDEX_FILE)

    with open(FAISS_MAPPING_FILE, "wb") as f:
        pickle.dump(mapping, f)

    print(f"[FAISS] Stored {len(texts)} vectors for sow_id={sow_id} "
          f"| reference_msa={reference_msa} | Status: {status} | start_timestamp: {mapping[-1]['start_timestamp']}")
    return status


# ─────────────────────────────────────────────
# 🔎 SEARCH FAISS (semantic similarity lookup)
# ─────────────────────────────────────────────
def search_faiss(query: str, top_k: int = 5) -> list[dict]:
    """
    Returns top-k mapping entries whose stored texts are
    semantically closest to the query string.
    Searches ACTIVE records only (active_flag == 1).

    Useful for finding SOWs by clause content, e.g.:
        search_faiss("payment milestone 30 days")
    """
    index, mapping = load_faiss_store()

    if index is None or not mapping:
        print("[FAISS] No index found — nothing to search.")
        return []

    # ✅ Only search across active entries
    active_entries = [e for e in mapping if e.get("active_flag", 1) == 1]

    if not active_entries:
        print("[FAISS] No active records to search.")
        return []

    query_vec = model.encode([query])
    distances, indices = index.search(np.array(query_vec), top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0:
            continue
        # Map vector index back to a mapping entry (active only)
        cumulative = 0
        for entry in active_entries:
            chunk_count = len(entry["texts"])
            if cumulative + chunk_count > idx:
                results.append({
                    "sow_id"        : entry["sow_id"],
                    "reference_msa" : entry.get("reference_msa", ""),
                    "distance"      : round(float(dist), 4),
                    "matched_text"  : entry["texts"][idx - cumulative],
                    "start_timestamp": entry.get("start_timestamp"),   # ← included for traceability
                })
                break
            cumulative += chunk_count

    return results