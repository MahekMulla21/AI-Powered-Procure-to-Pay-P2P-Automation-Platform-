"""
rag/rag_formatter.py
====================
Formats FAISS search results into a human-readable context string
for injection into the LLM decision prompt.

Mapping entries from Invoice_faiss_store look like:
    {"invoice_number": "INV-001", "texts": ["Description of Service: ..."]}

This module extracts the texts field and formats them cleanly.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("rag.rag_formatter")


def format_context(chunks: list[Any]) -> str:
    """
    Format a list of FAISS mapping entries into a readable context string.

    Handles three chunk formats:
      1. dict with "texts" key  → {"invoice_number": ..., "texts": [...]}
      2. dict without "texts"   → arbitrary dict, rendered as key=value
      3. plain string           → used directly

    Args:
        chunks: List returned by rag_search.retrieve_context().

    Returns:
        Formatted multi-section string, or "No relevant context found."
    """
    if not chunks:
        return "No relevant context found."

    sections: list[str] = []

    for i, chunk in enumerate(chunks, 1):
        try:
            text = _chunk_to_text(chunk)
            if text:
                sections.append(f"[Context {i}]\n{text}")
        except Exception as exc:
            logger.warning("[RAGFormatter] Failed to format chunk %d: %s", i, exc)

    if not sections:
        return "No relevant context found."

    logger.info("[RAGFormatter] Formatted %d context section(s)", len(sections))
    return "\n\n".join(sections)


def _chunk_to_text(chunk: Any) -> str:
    """Convert a single mapping entry to a plain-text string."""

    if isinstance(chunk, str):
        return chunk.strip()

    if isinstance(chunk, dict):
        parts: list[str] = []

        # Include metadata header if invoice_number is present
        inv_no = chunk.get("invoice_number") or chunk.get("doc_id")
        if inv_no:
            parts.append(f"Reference: {inv_no}")

        doc_type = chunk.get("doc_type")
        if doc_type:
            parts.append(f"Document type: {doc_type}")

        # Main text content
        texts = chunk.get("texts", [])
        if isinstance(texts, list):
            for t in texts:
                if t and str(t).strip():
                    parts.append(str(t).strip())
        elif isinstance(texts, str) and texts.strip():
            parts.append(texts.strip())

        # Fallback: render remaining keys if no texts field
        if not texts:
            skip = {"invoice_number", "doc_id", "doc_type",
                    "start_timestamp", "end_timestamp", "active_flag"}
            for k, v in chunk.items():
                if k not in skip and v is not None and str(v).strip():
                    parts.append(f"{k}: {v}")

        return "\n".join(parts)

    # Fallback for any other type
    return str(chunk).strip()