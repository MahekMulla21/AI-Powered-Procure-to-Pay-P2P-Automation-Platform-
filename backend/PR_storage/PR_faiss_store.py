import os
import faiss
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer


# ===============================
# MODEL
# ===============================
model = SentenceTransformer('all-MiniLM-L6-v2')

# ===============================
# PATHS
# ===============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "faiss_db", "output")
FAISS_INDEX_FILE = os.path.join(OUTPUT_DIR,"global_faiss.index")
FAISS_MAPPING_FILE = os.path.join(
    OUTPUT_DIR,
    "global_faiss_mapping.pkl"
)



# ===============================
# STORE IN FAISS
# ===============================
def store_in_faiss(unstructured, pr_id=None, status=None, file_id=None):
    """
    Store PR unstructured fields into FAISS index.

    Args:
        unstructured (dict): Unstructured PR fields
        pr_id (str):         PR ID for mapping reference
        status (str):        Match status (NEW / REVIEW_REQUIRED)
        file_id (int):       File ID from files_dataset
    """

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ===============================
    # BUILD TEXT CHUNKS
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

    print(f"\n📦 [FAISS] Storing {len(texts)} PR unstructured fields")
    print(f"   PR ID   : {pr_id}")
    print(f"   File ID : {file_id}")
    print(f"   Status  : {status}")

    # ===============================
    # ENCODE EMBEDDINGS
    # ===============================
    embeddings = model.encode(texts)

    dim = embeddings.shape[1]

    # ===============================
    # BUILD OR LOAD FAISS INDEX
    # ===============================
    if os.path.exists(FAISS_INDEX_FILE):
        print(f"   📂 Loading existing FAISS index: {FAISS_INDEX_FILE}")
        index = faiss.read_index(FAISS_INDEX_FILE)
    else:
        print(f"   🆕 Creating new FAISS index (dim={dim})")
        index = faiss.IndexFlatL2(dim)

    # ===============================
    # ADD EMBEDDINGS
    # ===============================
    index.add(np.array(embeddings, dtype=np.float32))

    # ===============================
    # SAVE FAISS INDEX
    # ===============================
    faiss.write_index(index, FAISS_INDEX_FILE)
    print(f"   ✅ FAISS index saved → {FAISS_INDEX_FILE}")

    # ===============================
    # BUILD MAPPING ENTRY
    # ===============================
    mapping_entry = {
        "pr_id": pr_id,
        "file_id": file_id,
        "status": status,
        "texts": texts
    }

    # ===============================
    # LOAD OR INIT MAPPING
    # ===============================
    if os.path.exists(FAISS_MAPPING_FILE):
        with open(FAISS_MAPPING_FILE, "rb") as f:
            mapping = pickle.load(f)
    else:
        mapping = []

    mapping.append(mapping_entry)

    # ===============================
    # SAVE MAPPING
    # ===============================
    with open(FAISS_MAPPING_FILE, "wb") as f:
        pickle.dump(mapping, f)

    print(f"   ✅ FAISS mapping saved → {FAISS_MAPPING_FILE}")


# ===============================
# CHECK EXISTING FAISS RECORD
# ===============================
def check_existing_faiss_record(pr_id, texts, threshold=0.3):
    """
    Check if a PR record already exists in FAISS.

    Args:
        pr_id     (str):   PR ID to check
        texts     (list):  Unstructured text chunks
        threshold (float): Distance threshold for duplicate detection

    Returns:
        "DUPLICATE"       → same pr_id + content within threshold
        "REVIEW_REQUIRED" → same pr_id but content differs
        "NEW"             → not found in index
    """

    if not os.path.exists(FAISS_INDEX_FILE):
        print("[FAISS CHECK] No index found → NEW")
        return "NEW"

    if not os.path.exists(FAISS_MAPPING_FILE):
        print("[FAISS CHECK] No mapping found → NEW")
        return "NEW"

    try:

        # ===============================
        # LOAD INDEX + MAPPING
        # ===============================
        index = faiss.read_index(FAISS_INDEX_FILE)

        with open(FAISS_MAPPING_FILE, "rb") as f:
            mapping = pickle.load(f)

        if index.ntotal == 0:
            print("[FAISS CHECK] Empty index → NEW")
            return "NEW"

        # ===============================
        # ENCODE INCOMING TEXTS
        # ===============================
        query_embeddings = model.encode(texts)

        # ===============================
        # SEARCH FAISS
        # ===============================
        distances, indices = index.search(
            np.array(query_embeddings, dtype=np.float32),
            k=1
        )

        for dist_row, idx_row in zip(distances, indices):

            dist = dist_row[0]
            idx  = idx_row[0]

            if idx < 0 or idx >= len(mapping):
                continue

            matched_entry  = mapping[idx]
            matched_pr_id  = matched_entry.get("pr_id")

            print(
                f"[FAISS CHECK] Matched PR ID : {matched_pr_id} "
                f"| Input PR ID : {pr_id} "
                f"| Distance    : {round(float(dist), 4)}"
            )

            # ===============================
            # SAME PR ID + WITHIN THRESHOLD
            # → DUPLICATE
            # ===============================
            if matched_pr_id == pr_id and dist <= threshold:
                print("[FAISS CHECK] → DUPLICATE")
                return "DUPLICATE"

            # ===============================
            # SAME PR ID + CONTENT DIFFERS
            # → REVIEW REQUIRED
            # ===============================
            if matched_pr_id == pr_id and dist > threshold:
                print("[FAISS CHECK] → REVIEW_REQUIRED")
                return "REVIEW_REQUIRED"

        print("[FAISS CHECK] → NEW")
        return "NEW"

    except Exception as e:
        print(f"[ERROR] FAISS check failed: {e}")
        return "NEW"


# ===============================
# VERIFY FAISS STORE
# ===============================
def verify_faiss_store():
    """
    Verify stored FAISS index and mapping.
    Prints all stored PR unstructured records.
    """

    print("\n🔍 [FAISS VERIFY] Checking PR FAISS store...\n")

    # ===============================
    # CHECK INDEX
    # ===============================
    if not os.path.exists(FAISS_INDEX_FILE):
        print(f"❌ FAISS index not found: {FAISS_INDEX_FILE}")
        return

    index = faiss.read_index(FAISS_INDEX_FILE)
    print(f"✅ FAISS Index loaded")
    print(f"   Total vectors stored : {index.ntotal}")
    print(f"   Dimension            : {index.d}")

    # ===============================
    # CHECK MAPPING
    # ===============================
    if not os.path.exists(FAISS_MAPPING_FILE):
        print(f"❌ FAISS mapping not found: {FAISS_MAPPING_FILE}")
        return

    with open(FAISS_MAPPING_FILE, "rb") as f:
        mapping = pickle.load(f)

    print(f"   Total mapping records: {len(mapping)}\n")

    # ===============================
    # PRINT RECORDS
    # ===============================
    for idx, entry in enumerate(mapping, start=1):

        print(f"── Record {idx} ──────────────────────────")
        print(f"   PR ID   : {entry.get('pr_id', 'NA')}")
        print(f"   File ID : {entry.get('file_id', 'NA')}")
        print(f"   Status  : {entry.get('status', 'NA')}")
        print(f"   Texts   :")

        for text in entry.get("texts", []):
            print(f"      → {text}")

        print()

    print("✅ [FAISS VERIFY] Done.\n")


# ===============================
# SEARCH FAISS
# ===============================
def search_faiss(query, top_k=3):
    """
    Search FAISS index for similar PR unstructured records.

    Args:
        query (str): Search query text
        top_k (int): Number of top results to return
    """

    print(f"\n🔎 [FAISS SEARCH] Query: {query}")

    if not os.path.exists(FAISS_INDEX_FILE):
        print("❌ FAISS index not found")
        return []

    if not os.path.exists(FAISS_MAPPING_FILE):
        print("❌ FAISS mapping not found")
        return []

    # ===============================
    # LOAD INDEX + MAPPING
    # ===============================
    index = faiss.read_index(FAISS_INDEX_FILE)

    with open(FAISS_MAPPING_FILE, "rb") as f:
        mapping = pickle.load(f)

    # ===============================
    # ENCODE QUERY
    # ===============================
    query_embedding = model.encode([query])

    # ===============================
    # SEARCH
    # ===============================
    distances, indices = index.search(
        np.array(query_embedding, dtype=np.float32),
        top_k
    )

    results = []

    for rank, (dist, idx) in enumerate(
        zip(distances[0], indices[0]), start=1
    ):

        if idx < len(mapping):

            entry = mapping[idx]

            result = {
                "rank": rank,
                "distance": round(float(dist), 4),
                "pr_id": entry.get("pr_id", "NA"),
                "file_id": entry.get("file_id", "NA"),
                "texts": entry.get("texts", [])
            }

            results.append(result)

            print(f"\n   Rank {rank} | Distance: {result['distance']}")
            print(f"   PR ID   : {result['pr_id']}")
            print(f"   File ID : {result['file_id']}")

            for text in result["texts"]:
                print(f"      → {text}")

    return results


# ===============================
# MAIN — VERIFY ON RUN
# ===============================
if __name__ == "__main__":
    verify_faiss_store()