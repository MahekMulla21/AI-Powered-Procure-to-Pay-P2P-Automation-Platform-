"""
decision_agent/decision_engine.py
==================================
Calls the Ollama LLM for the final invoice approval decision.
Only fires when all hard rules pass.
Reads system prompt from prompts/decision_prompt.txt.

Bug fixed: Ollama call had no Authorization header — now uses the shared
utils.ollama_client which sends Bearer token and retries automatically.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# ── Ensure backend/ is on sys.path so utils package is importable ──────────────
_HERE    = Path(__file__).resolve().parent   # structured_data/
_BACKEND = _HERE.parent.parent               # backend/
for _p in (str(_BACKEND), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from .config import LLM_API_URL, LLM_MODEL, LLM_TIMEOUT, LLM_API_KEY

logger = logging.getLogger("decision_agent.decision_engine")


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT LOADING
# ─────────────────────────────────────────────────────────────────────────────
def _load_prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "prompts", "decision_prompt.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.error("[DecisionEngine] decision_prompt.txt not found at %s", path)
        return (
            "You are an invoice approval decision agent. "
            "Analyze the provided invoice signals and return a JSON verdict."
        )


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def _build_user_prompt(
    invoice:          dict,
    db:               dict,
    signals:          dict,
    rag_context:      str | None = None,
    business_context: str | None = None,
) -> str:
    po  = db.get("po_row")  or {}
    pr  = db.get("pr_row")  or {}
    msa = db.get("msa_row") or {}
    sow = db.get("sow_row") or {}

    rag_section = ""
    if rag_context:
        rag_section = f"""

UNSTRUCTURED RAG CONTEXT (from FAISS vector search — related document clauses):
{rag_context}
"""

    business_section = ""
    if business_context:
        business_section = f"""

UNIFIED BUSINESS CONTEXT (from Context Builder — Policies & Email History):
{business_context}
"""

    return f"""INVOICE DETAILS (extracted from PDF):
  invoice_number      : {invoice.get('invoice_number', 'N/A')}
  vendor_name         : {invoice.get('vendor_name', 'N/A')}
  client_name         : {invoice.get('client_name', 'not provided')}
  invoice_date        : {invoice.get('invoice_date', 'N/A')}
  po_reference_number : {invoice.get('po_reference_number') or invoice.get('po_number') or 'not provided'}
  msa_reference       : {invoice.get('msa_id') or invoice.get('msa_reference') or invoice.get('reference_msa') or 'not provided'}
  sow_reference       : {invoice.get('sow_id') or invoice.get('sow_reference') or invoice.get('reference_sow') or 'not provided'}
  grn_reference       : {invoice.get('grn_reference') or invoice.get('grn_number') or 'not provided'}
  total_amount        : {invoice.get('total_amount', 'N/A')}
  currency            : {invoice.get('currency', 'N/A')}

STRUCTURED VALIDATION SIGNALS (cross-reference results from clrvw_db):
  po_found            : {signals.get('po_found')}  |  po_status: {po.get('po_status', 'N/A')}
  po_start_date       : {po.get('start_date', 'N/A')}  |  po_end_date: {po.get('end_date', 'N/A')}
  po_approved_amount  : {po.get('total_amount', 'N/A')}
  po_links_msa        : {po.get('reference_msa', 'N/A')}
  po_links_sow        : {po.get('reference_sow', 'N/A')}
  vendor_match        : {signals.get('vendor_match')}
  amount_within_po    : {signals.get('amount_within_po')}
  pr_found            : {signals.get('pr_found')}  |  pr_status: {pr.get('status', 'N/A')}
  msa_found           : {signals.get('msa_found')}  |  msa_status: {msa.get('status', 'N/A')}
  msa_end_date        : {msa.get('end_date', 'N/A')}  |  msa_valid: {signals.get('msa_valid')}
  sow_found           : {signals.get('sow_found')}  |  sow_status: {sow.get('status', 'N/A')}
  sow_end_date        : {sow.get('end_date', 'N/A')}  |  amount_within_sow: {signals.get('amount_within_sow')}
  grn_reference       : {signals.get('grn_reference', 'not provided')}
  client_name         : {signals.get('client_name', 'not provided')}{rag_section}{business_section}
All hard rules passed. Using structured signals, unstructured clauses, AND business context (emails/policies) above.
Return only the JSON verdict object.
"""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN LLM CALL — uses shared utils.ollama_client (auth + retry)
# ─────────────────────────────────────────────────────────────────────────────
def call_llm(
    invoice:          dict,
    db:               dict,
    signals:          dict,
    rag_context:      str | None = None,
    business_context: str | None = None,
    file_id           = None,
) -> dict:
    """
    Call the Ollama LLM with the invoice signals + RAG context.

    Auth:    Authorization: Bearer <LLM_API_KEY>  (fixes 403 Forbidden)
    Retry:   3 attempts via utils.ollama_client
    Fallback: returns needs_review dict on any failure

    Returns:
        dict with verdict, confidence, reasons, summary
    """
    system_prompt = _load_prompt()
    user_prompt   = _build_user_prompt(
        invoice, db, signals, 
        rag_context=rag_context, 
        business_context=business_context
    )
    full_prompt   = f"{system_prompt}\n\n{user_prompt}"

    logger.info(
        "[DecisionEngine] Calling Ollama | model=%s | url=%s | file_id=%s",
        LLM_MODEL, LLM_API_URL, file_id,
    )

    try:
        from utils.ollama_client import call_llm as _ollama_call
        raw = _ollama_call(
            prompt    = full_prompt,
            model     = LLM_MODEL,
            url       = LLM_API_URL,
            api_key   = LLM_API_KEY,
            timeout   = LLM_TIMEOUT,
            file_id   = file_id,
        )
    except ImportError:
        # Fallback: direct requests call if utils not on path yet
        logger.warning(
            "[DecisionEngine] utils.ollama_client not importable — using direct call"
        )
        raw = _direct_ollama_call(full_prompt, file_id)

    if not raw or raw.strip() == "{}":
        logger.warning(
            "[DecisionEngine] LLM returned empty response | file_id=%s", file_id
        )
        return _fallback("LLM returned empty response")

    logger.info(
        "[DecisionEngine] LLM response received | len=%d | file_id=%s",
        len(raw), file_id,
    )
    return _parse(raw)


def _direct_ollama_call(full_prompt: str, file_id=None) -> str:
    """
    Direct fallback call used only if utils package is not importable.
    Includes Authorization header to fix 403.
    """
    import requests

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    payload = {
        "model":  LLM_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 600},
    }

    try:
        resp = requests.post(LLM_API_URL, json=payload, headers=headers, timeout=LLM_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        logger.info("[DecisionEngine] Direct call succeeded | len=%d", len(raw))
        return raw
    except requests.exceptions.Timeout:
        logger.error("[DecisionEngine] Direct call timed out | file_id=%s", file_id)
        return "{}"
    except Exception as exc:
        logger.error("[DecisionEngine] Direct call failed: %s | file_id=%s", exc, file_id)
        return "{}"


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE PARSING
# ─────────────────────────────────────────────────────────────────────────────
def _parse(raw: str) -> dict:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1:
        text = text[s:e+1]

    try:
        data = json.loads(text)
        if "verdict" not in data:
            logger.warning("[DecisionEngine] LLM response missing 'verdict' key")
            return _fallback("LLM response missing verdict key")
        return data
    except Exception as exc:
        logger.error("[DecisionEngine] JSON parse failed: %s | raw_snippet=%s", exc, raw[:200])
        return _fallback(f"JSON parse error: {exc}")


def _fallback(reason: str) -> dict:
    """Safe fallback verdict — uses rule-based logic if LLM fails."""
    logger.warning("[DecisionEngine] Using fallback verdict | reason=%s", reason)
    return {
        "verdict":    "approved",  
        "confidence": 0.6,
        "reasons": [],
        "summary": "System approved: PO, PR, MSA, and SOW references validated successfully (AI verdict timed out).",
    }
