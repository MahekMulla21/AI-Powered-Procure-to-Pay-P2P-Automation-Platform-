"""
rag/rag_search.py
=================
Semantic search against the FAISS vector index.

Bug fixed: mapping.get(idx) crashed with 'list object has no attribute get'
           because Invoice_faiss_store.py stores mapping as a Python LIST,
           not a dict. FAISS returns integer vector indices — we use them
           as list indices with bounds-checking, not as dict keys.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from .embedding_model import model
from .vector_loader import load_vector_db

logger = logging.getLogger("rag.rag_search")


def retrieve_context(
    query:        str,
    index_path:   str,
    mapping_path: str,
    top_k:        int = 5,
) -> list[Any]:
    """
    Query the FAISS index and return the top-k matching metadata entries.

    Args:
        query:        Text query string (built from invoice fields).
        index_path:   Absolute path to the .index file.
        mapping_path: Absolute path to the .pkl mapping file.
        top_k:        Number of results to return.

    Returns:
        List of mapping entries (dicts). Empty list on any failure.
    """
    # ── Load index and mapping ────────────────────────────────────────────────
    index, mapping = load_vector_db(index_path, mapping_path)

    if index is None:
        logger.info("[RAGSearch] No FAISS index loaded — returning empty results")
        return []

    # mapping is guaranteed to be a list (or []) by load_vector_db
    if not mapping:
        logger.info("[RAGSearch] Mapping is empty — returning empty results")
        return []

    mapping_len = len(mapping)
    logger.info(
        "[RAGSearch] Searching index | query_len=%d | mapping_entries=%d | top_k=%d",
        len(query), mapping_len, top_k,
    )

    # ── Encode query ──────────────────────────────────────────────────────────
    try:
        embedding = model.encode([query])
        query_vec = np.array(embedding).astype("float32")
    except Exception as exc:
        logger.error("[RAGSearch] Failed to encode query: %s", exc)
        return []

    # ── Search ────────────────────────────────────────────────────────────────
    try:
        # Clamp top_k to BOTH available vectors AND mapping entries.
        # The index may have more vectors than mapping entries when old FAISS
        # stores accumulated orphaned vectors — mapping is the source of truth.
        effective_k = min(top_k, index.ntotal, mapping_len)
        if effective_k == 0:
            logger.warning("[RAGSearch] FAISS index has 0 usable vectors")
            return []

        _distances, indices = index.search(query_vec, effective_k)
    except Exception as exc:
        logger.error("[RAGSearch] FAISS search failed: %s", exc)
        return []

    # ── Collect results ───────────────────────────────────────────────────────
    results: list[Any] = []

    for idx in indices[0]:
        # FAISS uses -1 as a sentinel for "no result"
        if idx == -1:
            continue

        # BUG FIX: mapping is a LIST — use integer indexing, not .get()
        if isinstance(mapping, list):
            if 0 <= idx < mapping_len:
                chunk = mapping[idx]
                results.append(chunk)
            else:
                logger.warning(
                    "[RAGSearch] Index %d out of bounds for mapping (len=%d) — skipping",
                    idx, mapping_len,
                )
        elif isinstance(mapping, dict):
            # Backward-compat: old mapping format stored as {int: entry}
            chunk = mapping.get(idx)
            if chunk is not None:
                results.append(chunk)
        else:
            logger.error(
                "[RAGSearch] Unexpected mapping type: %s", type(mapping).__name__
            )
            break

    logger.info("[RAGSearch] Retrieved %d result(s)", len(results))
    return results