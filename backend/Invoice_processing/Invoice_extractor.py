# Invoice_extractor.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.Invoice_data.Invoice_field_definitions import (
    STRUCTURED_FIELD_DEFINITIONS,
    UNSTRUCTURED_FIELD_DEFINITIONS,
)
from backend.Invoice_llm.Invoice_llm import (
    call_llm,
    build_extraction_prompt,
    build_unstructured_prompt,
)
from backend.Invoice_processing.Invoice_faiss import TF_IDF_FAISS


# ── Dictionary anchor search ─────────────────────────────────────

def _anchor_search(lines: list[str], anchor_keys: list[str]) -> str:
    """
    Walk every line of the OCR text.
    When an anchor keyword is found (substring, case-insensitive),
    collect that line plus the next 4 lines as a context window.

    Args:
        lines       : All lines of the raw OCR text.
        anchor_keys : Ordered list of label strings from field definition.

    Returns:
        Deduplicated, newline-joined context string.
        Empty string if no anchor was found.
    """
    collected : list[str] = []
    seen      : set[str]  = set()

    for idx, line in enumerate(lines):
        for anchor in anchor_keys:
            if anchor.lower() in line.lower():       # substring match, no regex
                window = lines[idx : idx + 5]
                for ln in window:
                    if ln not in seen:
                        seen.add(ln)
                        collected.append(ln)
                break   # one anchor per line is sufficient

    return "\n".join(collected)


# ── Structured field extraction ───────────────────────────────────

def extract_structured_fields(
    raw_text   : str,
    faiss_index: TF_IDF_FAISS,
) -> dict[str, str]:
    """
    Extract every structured field defined in STRUCTURED_FIELD_DEFINITIONS.

    Pipeline per field:
      1. Run dictionary anchor search on raw lines.
      2. If no anchor hit → run FAISS semantic search as fallback.
      3. Send retrieved context + llm_hint to the LLM.
      4. Store the LLM's reply.

    Args:
        raw_text    : Full OCR-extracted text.
        faiss_index : Pre-built TF_IDF_FAISS index over text chunks.

    Returns:
        Dict mapping field name → extracted value string.
    """
    lines   = raw_text.splitlines()
    results : dict[str, str] = {}

    for field, meta in STRUCTURED_FIELD_DEFINITIONS.items():

        # Step 1 – Anchor (dictionary) search
        context = _anchor_search(lines, meta["anchor_keys"])

        # Step 2 – FAISS semantic fallback
        if not context.strip():
            top     = faiss_index.search(meta["query"], top_k=2)
            context = " | ".join(chunk for _, chunk in top if chunk.strip())

        # Step 3 – LLM extraction
        prompt        = build_extraction_prompt(context, meta["llm_hint"])
        results[field] = call_llm(prompt)

    return results


# ── Unstructured field extraction ────────────────────────────────

def extract_unstructured_fields(
    raw_text   : str,
    faiss_index: TF_IDF_FAISS,
) -> dict[str, str]:
    """
    Extract every unstructured field defined in UNSTRUCTURED_FIELD_DEFINITIONS.

    Pipeline per field:
      1. FAISS semantic search with field-specific query.
      2. Concatenate top-k chunks as context.
      3. Send context + llm_hint to LLM for narrative generation.

    Args:
        raw_text    : Full OCR-extracted text.
        faiss_index : Pre-built TF_IDF_FAISS index over text chunks.

    Returns:
        Dict mapping field name → generated text.
    """
    results: dict[str, str] = {}

    for field, meta in UNSTRUCTURED_FIELD_DEFINITIONS.items():
        top     = faiss_index.search(meta["query"], top_k=meta.get("top_k", 4))
        context = "\n".join(chunk for _, chunk in top)
        prompt  = build_unstructured_prompt(context, meta["llm_hint"])
        results[field] = call_llm(prompt)

    return results
