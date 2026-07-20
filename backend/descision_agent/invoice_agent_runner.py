"""
invoice_agent_runner.py
========================
Entry point for the Invoice Decision pipeline (/upload-invoice endpoint).

This runner is SEPARATE from the normal invoice pipeline:
  - /upload           → invoice_main.process_file()  [DB + FAISS storage]
  - /upload-invoice   → invoice_agent_runner.run()   [decision only, no DB write]

Flow:
  Stage 1 — invoice_agent.agent_extractor.extract()
            Uses Invoice_ocr, Invoice_processing, Invoice_llm modules.
            Fast LLM (30s timeout, 1 attempt) + immediate rule fallback.
            Does NOT write to DB or FAISS.

  Stage 2 — RAG search (FAISS)
            Builds a rich query from: vendor, PO, MSA, SOW, GRN, description.
            Retrieves top-k unstructured context chunks for LLM context.

  Stage 3 — decision_agent.agent_main.run()
            Hard rules: PO / PR / MSA / SOW cross-reference checks.
            Instant REJECT on any violation.
            If all pass → LLM call with signals + RAG context → verdict.

Call this from the FastAPI /upload-invoice endpoint.
DO NOT import at module level (lazy import keeps server startup fast).
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger("invoice_agent_runner")

# ── Resolve directories ────────────────────────────────────────────────────────
_THIS    = Path(__file__).resolve().parent     # backend/descision_agent/
_BACKEND = _THIS.parent                        # backend/
_SD      = _THIS / "structured_data"          # backend/descision_agent/structured_data/
_RAG     = _THIS / "rag"                      # backend/descision_agent/rag/
_AGENT   = _THIS / "invoice_agent"            # backend/descision_agent/invoice_agent/

# FAISS files
FAISS_INDEX_FILE   = str(_BACKEND / "faiss_db" / "output" / "global_faiss.index")
FAISS_MAPPING_FILE = str(_BACKEND / "faiss_db" / "output" / "global_faiss_mapping.pkl")


# ── Register decision_agent package ───────────────────────────────────────────
def _register_packages() -> None:
    """
    Register structured_data/ as the 'decision_agent' package and
    add all required directories to sys.path.
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

    for _p in [str(_BACKEND), str(_THIS), str(_AGENT)]:
        if _p not in sys.path:
            sys.path.insert(0, _p)


# ── Stage 2: RAG context retrieval ───────────────────────────────────────────
def _get_rag_context(structured: dict, top_k: int = 5) -> str:
    """
    Build a multi-field query from extracted invoice fields and
    retrieve relevant unstructured context from FAISS.
    """
    try:
        if str(_THIS) not in sys.path:
            sys.path.insert(0, str(_THIS))

        from rag.rag_search import retrieve_context
        from rag.rag_formatter import format_context

        query_parts: list[str] = []
        for field in (
            "vendor_name", "description_of_service",
            "po_reference_number", "msa_id", "sow_id",
            "grn_reference",
        ):
            val = structured.get(field)
            if val:
                query_parts.append(str(val).strip())

        if not query_parts:
            logger.info("[RAG] No query fields — skipping FAISS search")
            return "No relevant unstructured context available."

        query = " | ".join(query_parts)
        logger.info("[RAG] Query: %s", query[:120])

        chunks  = retrieve_context(query, FAISS_INDEX_FILE, FAISS_MAPPING_FILE, top_k=top_k)
        context = format_context(chunks)
        logger.info("[RAG] Retrieved %d chunk(s)", len(chunks))
        return context

    except FileNotFoundError:
        logger.warning("[RAG] FAISS index not found — skipping")
        return "No RAG index available yet."
    except Exception as exc:
        logger.warning("[RAG] Search failed: %s", exc)
        return f"RAG search unavailable: {exc}"


# ── Public entry point ─────────────────────────────────────────────────────────
def run(file_path: str, file_id=None) -> dict:
    """
    Full invoice decision pipeline (no DB write).

    Args:
        file_path : absolute path to the invoice PDF
        file_id   : DB file ID from files_dataset (for audit logging only)

    Returns:
        dict with keys:
          extraction  — result from invoice_agent.agent_extractor.extract()
          rag_context — retrieved unstructured context string
          verdict     — full decision dict from decision_agent.agent_main.run()
    """
    _register_packages()

    result: dict = {
        "extraction":  {},
        "rag_context": "",
        "verdict":     {},
    }

    # ── Stage 1: Extract invoice fields (no DB write) ─────────────────────────
    try:
        from invoice_agent.agent_extractor import extract
        extraction = extract(file_path, file_id)
    except Exception as exc:
        logger.exception("[AgentRunner] Extraction exception: %s", exc)
        result["verdict"] = _error_verdict("EXTRACTION_EXCEPTION", str(exc))
        return result

    if not extraction:
        result["verdict"] = _error_verdict("EXTRACTION_FAILED", "Extractor returned no data.")
        return result

    if extraction.get("status") == "failed":
        error_msg = extraction.get("error", "Unknown extraction error")
        logger.error("[AgentRunner] Extraction failed: %s", error_msg)
        result["extraction"] = extraction
        result["verdict"]    = _error_verdict("EXTRACTION_FAILED", error_msg)
        return result

    result["extraction"] = extraction
    structured   = extraction.get("structured",   {})
    unstructured = extraction.get("unstructured", {})

    # Merge unstructured description into structured for RAG query building
    if unstructured:
        structured.setdefault(
            "description_of_service",
            unstructured.get("description_of_service", ""),
        )

    logger.info(
        "[AgentRunner] Extraction OK | invoice=%s | po=%s | msa=%s | sow=%s | file_id=%s",
        extraction.get("invoice_number"),
        structured.get("po_reference_number"),
        structured.get("msa_id"),
        structured.get("sow_id"),
        file_id,
    )

    # ── Stage 2: RAG context ──────────────────────────────────────────────────
    rag_context = _get_rag_context(structured)
    result["rag_context"] = rag_context

    # ── Stage 3: Decision agent ───────────────────────────────────────────────
    try:
        from decision_agent.agent_main import run as run_agent
        verdict = run_agent(structured, file_id=file_id, rag_context=rag_context)
        result["verdict"] = verdict
        logger.info(
            "[AgentRunner] Decision: %s (%.0f%%) | invoice=%s",
            verdict.get("verdict", "?").upper(),
            float(verdict.get("confidence", 0)) * 100,
            extraction.get("invoice_number"),
        )
    except Exception as exc:
        logger.exception("[AgentRunner] Decision agent exception: %s", exc)
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
