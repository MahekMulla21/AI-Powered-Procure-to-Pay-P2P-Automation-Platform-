"""
invoice_agent/agent_extractor.py
=================================
Invoice extraction module used exclusively by the decision pipeline.

Key differences from the standard invoice_main.process_file():
  - Does NOT write anything to the database or FAISS
  - Does NOT check for duplicates
  - Uses a SHORT LLM timeout (30s, 1 attempt) so it fails fast
    and falls back to rule-based extraction immediately
  - Returns the extracted dict directly (no status/file_id wrapping)
  - Also extracts MSA / SOW reference IDs which are needed by the
    decision agent for cross-reference checks

All actual extraction logic is shared with the standard pipeline
(Invoice_ocr, Invoice_processing, Invoice_llm modules).
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger("invoice_agent.extractor")

# ── Ensure backend/ is on sys.path so Invoice_* packages are importable ────────
_BACKEND = Path(__file__).resolve().parent.parent.parent   # backend/
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# ── Import from the shared Invoice_ pipeline ────────────────────────────────────
from Invoice_ocr.Invoice_pdf_text_extractor import extract_text_from_pdf
from utils.docx_text_extractor import extract_text_from_docx
from Invoice_ocr.Invoice_pdf_to_image import pdf_to_images
from Invoice_ocr.Invoice_paddle_ocr import extract_text as ocr_extract_text

from Invoice_processing.Invoice_pdf_detector import is_digital_pdf
from Invoice_processing.Invoice_rule_based_extractor import extract_with_rules
from Invoice_processing.Invoice_cleaner import clean_json
from Invoice_processing.Invoice_validator import validate

from Invoice_llm.Invoice_prompt_template import get_prompt

from Invoice_config.Invoice_settings import MODEL_NAME, API_URL, API_KEY

# ── Structured fields for the decision pipeline ─────────────────────────────────
# Includes the cross-reference fields (msa_id, sow_id) that the decision
# agent needs for lookups, even though they are not in the DB schema.
_STRUCTURED_FIELDS = [
    "invoice_number", "vendor_name", "client_name", "invoice_date", "due_date",
    "po_reference_number", "grn_reference", "hsn_code", "quantity",
    "unit_price", "total_amount", "tax", "currency", "company_code", "status",
    # Cross-reference IDs for decision agent
    "msa_id", "sow_id",
]
_UNSTRUCTURED_FIELDS = ["description_of_service", "tax_breakup", "bank_details"]


# ─────────────────────────────────────────────────────────────────────────────
# FAST LLM CALL  (short timeout, single attempt)
# ─────────────────────────────────────────────────────────────────────────────
def _call_llm_fast(prompt: str) -> str:
    """
    Call Ollama with a 30-second timeout and a single attempt.
    Returns '{}' immediately on failure so the extractor doesn't
    block the decision pipeline for 6+ minutes.
    """
    import requests
    from requests.exceptions import Timeout, ConnectionError

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    payload = {
        "model":  MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 2048},
    }

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response", "").strip()
        if text:
            logger.info("[AgentLLM] LLM responded | len=%d", len(text))
            return text
        logger.warning("[AgentLLM] LLM returned empty response")
        return "{}"
    except Timeout:
        logger.warning("[AgentLLM] LLM timed out (30s) — using rule-based fallback")
        return "{}"
    except ConnectionError as exc:
        logger.warning("[AgentLLM] LLM connection error: %s — using rule-based fallback", exc)
        return "{}"
    except Exception as exc:
        logger.warning("[AgentLLM] LLM error: %s — using rule-based fallback", exc)
        return "{}"


# ─────────────────────────────────────────────────────────────────────────────
# LAST-RESORT INVOICE NUMBER FALLBACK
# ─────────────────────────────────────────────────────────────────────────────
def _fallback_invoice_number(text: str, file_id) -> str:
    patterns = [
        r"(?:invoice\s*(?:no|number|#|num|id)[:\s#]*)([A-Z]{2,6}[-][A-Z]{0,4}[-]?\d{4}[-]\d+)",
        r"\b(INV[-][A-Z]{2,6}[-]\d{4}[-]\d+)\b",
        r"\b([A-Z]{2,6}[-]\d{4}[-]\d{4,})\b",
        r"(?:invoice\s*(?:no|number|#)[:\s]*)([A-Z0-9][A-Z0-9\-/]{3,20})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return f"INV-AUTO-{file_id}" if file_id else "INV-AUTO-UNKNOWN"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXTRACTION FUNCTION
# ─────────────────────────────────────────────────────────────────────────────
def extract(file_path: str, file_id=None) -> dict:
    """
    Extract all invoice fields from a PDF for use by the decision agent.

    This function mirrors invoice_main.process_file() but:
      - Does NOT save anything to the DB or FAISS
      - Uses a fast LLM call (30s timeout, 1 attempt)
      - Always returns the extracted dict — never raises

    Args:
        file_path : Absolute path to the PDF file
        file_id   : Optional file ID for logging context

    Returns:
        dict with keys:
          status          : "success" | "failed"
          structured      : dict of extracted structured fields
          unstructured    : dict of extracted unstructured fields
          invoice_number  : the extracted invoice number (shortcut)
          error           : error message (only when status="failed")
    """
    logger.info("[AgentExtractor] Starting extraction | file_id=%s | path=%s", file_id, file_path)

    if not os.path.exists(file_path):
        return {"status": "failed", "error": f"File not found: {file_path}", "file_id": file_id}

    # ── Step 1: Text extraction ───────────────────────────────────────────────
    text = ""
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".docx":
            logger.info("[AgentExtractor] DOCX file — using python-docx")
            text = extract_text_from_docx(file_path)
        elif ext == ".pdf":
            if is_digital_pdf(file_path):
                logger.info("[AgentExtractor] Digital PDF — using PyMuPDF")
                text = extract_text_from_pdf(file_path)
            else:
                logger.info("[AgentExtractor] Scanned PDF — using PaddleOCR")
                images = pdf_to_images(file_path)
                text = ocr_extract_text(images)
        else:
            logger.warning("[AgentExtractor] Unsupported file extension: %s", ext)
    except Exception as exc:
        logger.error("[AgentExtractor] Text extraction error: %s", exc)

    if not text or not text.strip():
        return {
            "status": "failed",
            "error":  f"No text could be extracted from the {ext} file.",
            "file_id": file_id,
        }

    logger.info("[AgentExtractor] Extracted %d characters", len(text))

    # ── Step 2: Rule-based extraction (always runs first) ────────────────────
    rule_data: dict = {}
    try:
        rule_data = extract_with_rules(text)
        logger.info("[AgentExtractor] Rule extraction done: %s", rule_data)
    except Exception as exc:
        logger.warning("[AgentExtractor] Rule extraction failed: %s", exc)

    # ── Step 3: LLM extraction (fast, single attempt) ────────────────────────
    raw_response = "{}"
    try:
        prompt = get_prompt(text, rule_data)
        raw_response = _call_llm_fast(prompt)
        logger.info("[AgentExtractor] LLM raw response (first 200): %s", raw_response[:200])
    except Exception as exc:
        logger.warning("[AgentExtractor] LLM call failed: %s", exc)

    # ── Step 4: Clean the JSON response ──────────────────────────────────────
    data: dict = {"structured": {}, "unstructured": {}}
    try:
        data = clean_json(raw_response)
    except Exception as exc:
        logger.warning("[AgentExtractor] JSON clean failed: %s", exc)

    # ── Step 4.5: Pre-merge rule_data BEFORE validate() ──────────────────────
    # This is the critical fix: ensures validate() sees real values, not {}
    llm_s = data.get("structured",   {})
    llm_u = data.get("unstructured", {})

    for field in _STRUCTURED_FIELDS:
        if not llm_s.get(field):
            val = rule_data.get(field)
            if val:
                llm_s[field] = val

    for field in _UNSTRUCTURED_FIELDS:
        if not llm_u.get(field):
            val = rule_data.get(field)
            if val:
                llm_u[field] = val

    data["structured"]   = llm_s
    data["unstructured"] = llm_u
    logger.info("[AgentExtractor] After rule pre-merge: %s", llm_s)

    # ── Step 5: Validate (only sets truly-missing fields to None) ─────────────
    try:
        data = validate(data)
    except Exception as exc:
        logger.warning("[AgentExtractor] Validation failed: %s", exc)

    structured   = data.get("structured",   {})
    unstructured = data.get("unstructured", {})

    # ── Step 5.5: Safety-net fallback ─────────────────────────────────────────
    if not any(v for v in structured.values() if v):
        logger.warning("[AgentExtractor] Safety-net: re-applying rule data")
        for field in _STRUCTURED_FIELDS:
            val = rule_data.get(field)
            if val:
                structured[field] = val
        for field in _UNSTRUCTURED_FIELDS:
            val = rule_data.get(field)
            if val:
                unstructured[field] = val
        data["structured"]   = structured
        data["unstructured"] = unstructured

    # ── Step 6: Ensure invoice_number is always set ───────────────────────────
    if not structured.get("invoice_number"):
        fallback = _fallback_invoice_number(text, file_id)
        structured["invoice_number"] = fallback
        logger.warning("[AgentExtractor] invoice_number fallback: %s", fallback)

    logger.info(
        "[AgentExtractor] Extraction complete | invoice=%s | po=%s | msa=%s | sow=%s",
        structured.get("invoice_number"),
        structured.get("po_reference_number"),
        structured.get("msa_id"),
        structured.get("sow_id"),
    )

    return {
        "status":         "success",
        "file_id":        file_id,
        "invoice_number": structured.get("invoice_number"),
        "structured":     structured,
        "unstructured":   unstructured,
    }
