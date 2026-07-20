"""
rag/vector_loader.py
====================
Loads the FAISS index + metadata mapping from disk.

Bug fixed: previously returned (None, None) when files were missing.
           rag_search.py only guarded against index being None, so when
           mapping was None the loop called None.get(idx) and crashed.
           Now returns (None, []) — an empty list is the safe sentinel.
"""

import logging
import os
import pickle

import faiss

logger = logging.getLogger("rag.vector_loader")


def load_vector_db(index_path: str, mapping_path: str):
    """
    Load FAISS index and metadata mapping from disk.

    Returns:
        (faiss.Index, list) on success
        (None, [])          when files do not exist yet — safe fallback
    """
    if not os.path.exists(index_path):
        logger.info(
            "[VectorLoader] FAISS index not found at %s — returning empty store",
            index_path,
        )
        return None, []

    if not os.path.exists(mapping_path):
        logger.warning(
            "[VectorLoader] Mapping file missing at %s — returning empty store",
            mapping_path,
        )
        return None, []

    try:
        index = faiss.read_index(index_path)
    except Exception as exc:
        logger.error("[VectorLoader] Failed to read FAISS index: %s", exc)
        return None, []

    try:
        with open(mapping_path, "rb") as f:
            mapping = pickle.load(f)
    except Exception as exc:
        logger.error("[VectorLoader] Failed to load mapping pickle: %s", exc)
        return None, []

    # Ensure mapping is always a list (older versions may have stored a dict)
    if isinstance(mapping, dict):
        logger.warning(
            "[VectorLoader] Mapping is a dict — converting to list for compatibility"
        )
        # dict was keyed by int → convert to list ordered by key
        mapping = [mapping[k] for k in sorted(mapping.keys())]

    logger.info(
        "[VectorLoader] Loaded FAISS index (%d vectors) + mapping (%d entries)",
        index.ntotal if hasattr(index, "ntotal") else -1,
        len(mapping),
    )
    return index, mapping