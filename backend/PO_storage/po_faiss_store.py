import faiss
import numpy as np
import pickle
import os
import re
from sentence_transformers import SentenceTransformer
from PO_config.po_settings import OUTPUT_DIR

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "faiss_db", "output")
FAISS_INDEX_FILE = os.path.join(OUTPUT_DIR,"global_faiss.index")
FAISS_MAPPING_FILE = os.path.join(
    OUTPUT_DIR,
    "global_faiss_mapping.pkl"
)


def clean_po_id(po_id):
    """Normalize po_id for comparison. Removes non-alphanumeric chars, lowercase."""
    if not po_id or str(po_id).strip() == "":
        return None
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', str(po_id))
    return cleaned.lower()

model = SentenceTransformer('all-MiniLM-L6-v2')

# ─────────────────────────────────────────────
# 📦 LOAD EXISTING FAISS INDEX + MAPPING
# ─────────────────────────────────────────────
# def load_faiss_store():
#     """Returns (index, mapping) or (None, []) if not found."""
#     print(f"[DEBUG FAISS LOAD] Checking files:")
#     print(f"[DEBUG FAISS LOAD] Index path: {FAISS_INDEX_FILE}")
#     print(f"[DEBUG FAISS LOAD] Mapping path: {FAISS_MAPPING_FILE}")
#     print(f"[DEBUG FAISS LOAD] Index exists: {os.path.exists(FAISS_INDEX_FILE)}")
#     print(f"[DEBUG FAISS LOAD] Mapping exists: {os.path.exists(FAISS_MAPPING_FILE)}")

#     if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(FAISS_MAPPING_FILE):
#         try:
#             index = faiss.read_index(FAISS_INDEX_FILE)
#             with open(FAISS_MAPPING_FILE, "rb") as f:
#                 mapping = pickle.load(f)
#             print(f"[DEBUG FAISS LOAD] Successfully loaded index ({index.ntotal} vectors) and mapping ({len(mapping)} entries)")
#             return index, mapping
#         except Exception as e:
#             print(f"[ERROR FAISS LOAD] Failed to load files: {e}")
#             return None, []
#     print(f"[DEBUG FAISS LOAD] Files not found, returning empty store")
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
def check_existing_faiss_record(po_id: str, new_texts: list[str]) -> str:
    """
    SCD Type 2: Only checks ACTIVE records for duplicate/review detection.
    Ignores historically deactivated entries.
    """
    try:
        _, mapping = load_faiss_store()

        po_id_clean = clean_po_id(po_id)
        for entry in mapping:
            entry_po_id_clean = clean_po_id(entry.get("po_id", ""))
            if entry_po_id_clean == po_id_clean and entry.get("active_flag", True):
                # ✅ Only compare against active version
                if entry.get("texts") == new_texts:
                    return "DUPLICATE"
                else:
                    return "REVIEW_REQUIRED"

        return "NEW"

    except Exception as e:
        print(f"[ERROR] FAISS check failed: {e}")
        return "NEW"

# ─────────────────────────────────────────────
# 🔥 DEACTIVATE (REMOVE) OLD FAISS RECORDS
# ─────────────────────────────────────────────
from datetime import datetime

def deactivate_old_faiss_records(po_id: str):
    """
    SCD Type 2: Mark old FAISS records as inactive instead of deleting them.
    Preserves vector history — does NOT rebuild index.
    """
    try:
        index, mapping = load_faiss_store()

        if not mapping:
            print("[INFO] No existing FAISS records to deactivate")
            return

        updated_count = 0
        po_id_clean = clean_po_id(po_id)
        for entry in mapping:
            entry_po_id_clean = clean_po_id(entry.get("po_id", ""))
            if entry_po_id_clean == po_id_clean and entry.get("active_flag", True):
                entry["active_flag"]    = 0
                entry["end_timestamp"]  = datetime.now().isoformat()
                updated_count += 1

        if updated_count == 0:
            print(f"[INFO] No active FAISS records found for po_id={po_id}")
            return

        # ✅ Persist updated mapping — index vectors stay untouched
        with open(FAISS_MAPPING_FILE, "wb") as f:
            pickle.dump(mapping, f)

        print(f"[SCD2-FAISS] Deactivated {updated_count} old record(s) for po_id={po_id}")

    except Exception as e:
        print(f"[ERROR] FAISS deactivation failed: {e}")

# ─────────────────────────────────────────────
# 💾 STORE IN FAISS (WITH DUPLICATE LOGIC)
# ─────────────────────────────────────────────
def store_in_faiss(unstructured: dict, po_id: str, vendor_name: str = None, status: str = None, file_id=None):
    try:
        # Debug log paths at start
        print(f"[DEBUG FAISS] Index file path: {FAISS_INDEX_FILE}")
        print(f"[DEBUG FAISS] Mapping file path: {FAISS_MAPPING_FILE}")
        print(f"[DEBUG FAISS] OUTPUT_DIR: {OUTPUT_DIR}")
        print(f"[DEBUG FAISS] OUTPUT_DIR exists: {os.path.exists(OUTPUT_DIR)}")

        description = unstructured.get('description_of_goods_and_services', '')
        texts = [
            f"Description of Goods and Services: {description}",
        ]

        # Debug log to show what's being stored
        print(f"[DEBUG] FAISS: Storing description of length {len(description)} characters")
        print(f"[DEBUG] FAISS: Description preview: {description[:200]}...")

        if status is None:
            print(f"[WARN] No status passed — running FAISS check independently")
            status = check_existing_faiss_record(po_id, texts)

        if file_id:
            print(f"[FAISS] Processing for file_id={file_id} | po_id={po_id}")

        if status == "DUPLICATE":
            print(f"[FAISS] Duplicate — skipping insert for po_id={po_id}")
            return status

        if status == "REVIEW_REQUIRED":
            print(f"[FAISS] Updated record — deactivating old vectors for po_id={po_id}")
            deactivate_old_faiss_records(po_id)  # ✅ now marks inactive, not deleted

        # ── Load existing store (post-deactivation) ──
        index, mapping = load_faiss_store()

        # ── Encode and add new vectors ──
        embeddings = model.encode(texts)
        dim = embeddings.shape[1]

        if index is None:
            index = faiss.IndexFlatL2(dim)

        index.add(np.array(embeddings))

        # ── Append new record WITH SCD2 metadata ──────────────
        mapping.append({
            "po_id":           po_id,
            "vendor_name":     vendor_name,
            "file_id":         file_id,
            "texts":           texts,
            "active_flag":     True,                        # ✅ currently active
            "start_timestamp": datetime.now().isoformat(),  # ✅ version start
            "end_timestamp":   None,                        # ✅ NULL = active
        })

        # ── Persist ──
        print(f"[DEBUG FAISS] Ensuring OUTPUT_DIR exists: {OUTPUT_DIR}")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # ✅ DEBUG: Show actual file paths
        print(f"[DEBUG FAISS] Saving index to: {FAISS_INDEX_FILE}")
        print(f"[DEBUG FAISS] Saving mapping to: {FAISS_MAPPING_FILE}")

        try:
            faiss.write_index(index, FAISS_INDEX_FILE)
            print(f"[DEBUG FAISS] Index file written successfully")
        except Exception as e:
            print(f"[ERROR FAISS] Failed to write index: {e}")
            raise

        try:
            with open(FAISS_MAPPING_FILE, "wb") as f:
                pickle.dump(mapping, f)
            print(f"[DEBUG FAISS] Mapping file written successfully")
        except Exception as e:
            print(f"[ERROR FAISS] Failed to write mapping: {e}")
            raise

        # Verify files were actually created
        index_exists = os.path.exists(FAISS_INDEX_FILE)
        mapping_exists = os.path.exists(FAISS_MAPPING_FILE)
        index_size = os.path.getsize(FAISS_INDEX_FILE) if index_exists else 0
        mapping_size = os.path.getsize(FAISS_MAPPING_FILE) if mapping_exists else 0

        print(f"[DEBUG FAISS] Verification - Index exists: {index_exists} ({index_size} bytes)")
        print(f"[DEBUG FAISS] Verification - Mapping exists: {mapping_exists} ({mapping_size} bytes)")

        if not index_exists or not mapping_exists:
            print(f"[ERROR FAISS] Files not found after writing!")
        else:
            print(f"[SCD2-FAISS] SUCCESS: Stored 1 active vector for po_id={po_id} | Status: {status}")

        return status

    except Exception as e:
        print(f"[ERROR] FAISS storage failed: {e}")
        print("[INFO] Pipeline continuing despite FAISS failure")
        return status