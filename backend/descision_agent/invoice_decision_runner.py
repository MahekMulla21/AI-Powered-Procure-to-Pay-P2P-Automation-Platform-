"""
invoice_decision_runner.py
==========================
Bridge module that wires three stages together:

  Stage 1 — invoice_main.process_file()
            OCR / LLM field extraction → Postgres + FAISS storage
            Returns structured + unstructured dicts.

  Stage 2 — RAG search (FAISS)
            Build a rich query from invoice key fields:
              vendor_name, msa_reference, sow_reference, po_reference,
              client_name, grn_reference, description_of_service
            Retrieve top-k unstructured context chunks.

  Stage 3 — decision_agent.agent_main.run()
            Structured checks: PO / PR / MSA / SOW / duplicate (Postgres)
            Hard rules engine → instant REJECT if any violation.
            LLM call with structured signals + RAG context → APPROVED /
            REJECTED / NEEDS_REVIEW with confidence + reasons.

Call this module from the FastAPI endpoint; do NOT import it at module level
to avoid slowing down server startup.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("invoice_decision_runner")

# ── Resolve directories ───────────────────────────────────────────────────────
_THIS     = Path(__file__).resolve().parent          # backend/descision_agent/
_BACKEND  = _THIS.parent                             # backend/
_SD       = _THIS / "structured_data"                # backend/descision_agent/structured_data/
_RAG      = _THIS / "rag"                            # backend/descision_agent/rag/

# FAISS files written by Invoice_faiss_store.py
FAISS_INDEX_FILE   = str(_BACKEND / "faiss_db" / "output" / "global_faiss.index")
FAISS_MAPPING_FILE = str(_BACKEND / "faiss_db" / "output" / "global_faiss_mapping.pkl")


# ── Register decision_agent package (structured_data/ → decision_agent) ───────
def _register_decision_agent_package() -> None:
    """
    The files in structured_data/ use `from decision_agent.xxx import yyy`.
    We register the structured_data/ directory as the `decision_agent` package
    so all internal cross-imports resolve correctly — without renaming folders.
    """
    if "decision_agent" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "decision_agent",
            str(_SD / "__init__.py"),
            submodule_search_locations=[str(_SD)],
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["decision_agent"] = mod
        spec.loader.exec_module(mod)

    # Add backend/ so invoice_main, pr_main etc. are importable
    for _p in [str(_BACKEND), str(_THIS)]:
        if _p not in sys.path:
            sys.path.insert(0, _p)


# ── Stage 2: RAG retrieval ────────────────────────────────────────────────────
def _get_rag_context(structured: dict, top_k: int = 5) -> str:
    """
    Query the FAISS index with a rich multi-field query built from:
      vendor_name, client_name, msa_reference, sow_reference,
      po_reference_number, grn_reference, description_of_service
    Returns formatted context string to inject into the LLM prompt.
    """
    try:
        # Add descision_agent/ to sys.path so `rag` package is importable
        if str(_THIS) not in sys.path:
            sys.path.insert(0, str(_THIS))

        from rag.rag_search import retrieve_context
        from rag.rag_formatter import format_context

        query_parts: list[str] = []
        for field in (
            "vendor_name", "client_name", "description_of_service",
            "po_reference_number", "po_number",
            "msa_id", "msa_reference", "reference_msa",
            "sow_id", "sow_reference", "reference_sow",
            "grn_reference", "grn_number",
        ):
            val = structured.get(field)
            if val:
                query_parts.append(str(val).strip())

        if not query_parts:
            logger.info("[RAG] No query fields found on invoice — skipping FAISS search")
            return "No relevant unstructured context available."

        query = " | ".join(query_parts)
        logger.info("[RAG] Query: %s", query[:120])

        chunks = retrieve_context(
            query,
            FAISS_INDEX_FILE,
            FAISS_MAPPING_FILE,
            top_k=top_k,
        )

        context = format_context(chunks)
        logger.info("[RAG] Retrieved %d chunk(s)", len(chunks))
        return context

    except FileNotFoundError:
        logger.warning("[RAG] FAISS index not found at %s — skipping", FAISS_INDEX_FILE)
        return "No RAG index available yet (FAISS index not built)."
    except Exception as exc:
        logger.warning("[RAG] Search failed: %s", exc)
        return f"RAG search unavailable: {exc}"


# ── Public entry point ────────────────────────────────────────────────────────
def run_invoice_decision(file_path: str, file_id=None) -> dict:
    """
    Full invoice decision pipeline.

    Args:
        file_path (str) : absolute path to the invoice PDF
        file_id   (int) : DB file ID (from files_dataset)

    Returns:
        dict with keys:
          extraction  — raw result from invoice_main.process_file()
          rag_context — retrieved unstructured context string
          verdict     — full decision dict from decision_agent.run()
    """
    _register_decision_agent_package()

    result: dict = {
        "extraction":  {},
        "rag_context": "",
        "verdict":     {},
    }

    # ── Stage 1: Extract invoice fields ──────────────────────────────────────
    try:
        from invoice_main import process_file
        extraction = process_file(file_path, file_id)
    except Exception as exc:
        logger.exception("[RUNNER] Extraction exception: %s", exc)
        result["verdict"] = _error_verdict("EXTRACTION_EXCEPTION", str(exc))
        return result

    # process_file now always returns a dict (never None)
    if not extraction:
        logger.error("[RUNNER] process_file returned None for file_id=%s", file_id)
        result["verdict"] = _error_verdict(
            "EXTRACTION_FAILED",
            "Invoice extraction returned no data.",
        )
        return result

    if extraction.get("status") == "failed":
        error_msg = extraction.get("error", "Unknown extraction error")
        logger.error("[RUNNER] Extraction failed for file_id=%s: %s", file_id, error_msg)
        result["extraction"] = extraction
        result["verdict"] = _error_verdict("EXTRACTION_FAILED", error_msg)
        return result

    if extraction.get("status") != "success":
        logger.error("[RUNNER] Unexpected extraction status=%s for file_id=%s",
                     extraction.get("status"), file_id)
        result["extraction"] = extraction
        result["verdict"] = _error_verdict(
            "EXTRACTION_FAILED",
            extraction.get("error", "Could not extract structured fields from the invoice PDF."),
        )
        return result

    result["extraction"] = extraction
    structured   = extraction.get("structured", {})
    unstructured = extraction.get("unstructured", {})

    # Merge unstructured text fields into structured for RAG query building
    if unstructured:
        structured.setdefault(
            "description_of_service",
            unstructured.get("description_of_service", ""),
        )

    logger.info(
        "[RUNNER] Extraction OK | invoice=%s | file_id=%s",
        extraction.get("invoice_number"), file_id,
    )

    # ── Stage 2: RAG context ─────────────────────────────────────────────────
    rag_context = _get_rag_context(structured)
    result["rag_context"] = rag_context

    # ── Stage 3: Decision agent ──────────────────────────────────────────────
    try:
        from decision_agent.agent_main import run as run_agent
        verdict = run_agent(structured, file_id=file_id, rag_context=rag_context)
        result["verdict"] = verdict
        logger.info(
            "[RUNNER] Decision: %s (%.0f%%) | invoice=%s",
            verdict.get("verdict", "?").upper(),
            float(verdict.get("confidence", 0)) * 100,
            extraction.get("invoice_number"),
        )
    except Exception as exc:
        logger.exception("[RUNNER] Decision agent exception: %s", exc)
        result["verdict"] = _error_verdict("AGENT_EXCEPTION", str(exc))

    return result


# ── Helpers ───────────────────────────────────────────────────────────────────
def _error_verdict(code: str, message: str) -> dict:
    return {
        "verdict":     "needs_review",
        "confidence":  0.0,
        "summary":     f"Pipeline error ({code}): {message}",
        "reasons": [{
            "code":    code,
            "field":   "pipeline",
            "value":   None,
            "message": message,
        }],
        "signals":     {},
        "rag_context": "",
    }
