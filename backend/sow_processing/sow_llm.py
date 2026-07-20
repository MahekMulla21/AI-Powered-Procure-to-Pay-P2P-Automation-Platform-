"""
sow_llm.py  —  Ollama LLM integration for SOW Pipeline
=======================================================
Calls the internal Ollama server (llama3) to enrich and
fill-in fields that rule-based extraction missed.

Config comes from sow_settings.py:
  OLLAMA_HOST  = http://10.1.1.219:11434
  OLLAMA_MODEL = llama3
  OLLAMA_TIMEOUT = 120

Usage:
  from sow_processing.sow_llm import enrich_with_llm
  enriched = enrich_with_llm(text, structured_data, unstructured_data)
"""

from __future__ import annotations
import json
import requests
from sow_config.sow_settings import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, API_KEY


# ─────────────────────────────────────────────────────────────
#  OLLAMA CONNECTION CHECK
# ─────────────────────────────────────────────────────────────

def check_ollama_connection() -> bool:
    """Ping the Ollama proxy to verify it is reachable."""
    try:
        # Hit the generate endpoint with a tiny test prompt
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {API_KEY}",
        }
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": "hi", "stream": False},
            headers=headers,
            timeout=15
        )
        if response.status_code in (200, 201):
            print(f"  [OLLAMA] Connected — {OLLAMA_URL}")
            return True
        else:
            print(f"  [OLLAMA] Server returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"  [OLLAMA] Connection failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────
#  CALL OLLAMA
# ─────────────────────────────────────────────────────────────

def _call_ollama(prompt: str) -> str:
    """
    Send a prompt to Ollama via the proxied API endpoint.
    Uses Bearer token authentication.
    """
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 1000,
        }
    }

    try:
        print(f"  [OLLAMA] Calling {OLLAMA_MODEL} at {OLLAMA_URL} ...")
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            headers=headers,
            timeout=OLLAMA_TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()

    except requests.exceptions.Timeout:
        print(f"  [OLLAMA] Request timed out after {OLLAMA_TIMEOUT}s")
        return ""
    except requests.exceptions.ConnectionError:
        print(f"  [OLLAMA] Cannot reach Ollama at {OLLAMA_URL}")
        return ""
    except Exception as e:
        print(f"  [OLLAMA] Error: {e}")
        return ""


# ─────────────────────────────────────────────────────────────
#  BUILD PROMPT
# ─────────────────────────────────────────────────────────────

def _build_prompt(text: str, existing: dict) -> str:
    """
    Build a focused prompt asking Ollama to extract only the
    fields that rule-based extraction missed (value is None/empty).
    """
    missing_fields = [k for k, v in existing.items() if not v]

    if not missing_fields:
        return ""  # Nothing to enrich

    fields_list = "\n".join(f"- {f}" for f in missing_fields)

    prompt = f"""You are a document extraction assistant. 
Extract the following fields from this Statement of Work (SOW) document.
Return ONLY a valid JSON object with the field names as keys.
If a field is not found, use null as the value.
Do NOT add any explanation or text outside the JSON.

Fields to extract:
{fields_list}

Document text:
\"\"\"
{text[:6000]}
\"\"\"

Return JSON only:"""

    return prompt


# ─────────────────────────────────────────────────────────────
#  PARSE LLM RESPONSE
# ─────────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict:
    """
    Safely parse the JSON response from Ollama.
    Handles common issues like extra text around the JSON.
    """
    if not raw:
        return {}

    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON block from response
    try:
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
    except json.JSONDecodeError:
        pass

    print(f"  [OLLAMA] Could not parse JSON from response")
    return {}


# ─────────────────────────────────────────────────────────────
#  PUBLIC FUNCTION — ENRICH WITH LLM
# ─────────────────────────────────────────────────────────────

def enrich_with_llm(
    text: str,
    structured: dict,
    unstructured: dict
) -> tuple[dict, dict]:
    """
    Use Ollama llama3 to fill in any fields that rule-based
    extraction missed.

    Args:
        text         : Full extracted PDF text
        structured   : Dict of structured fields from rule-based extraction
        unstructured : Dict of unstructured fields from rule-based extraction

    Returns:
        (enriched_structured, enriched_unstructured) — same dicts with
        missing values filled in where Ollama found them.
    """
    print(f"\n  [OLLAMA] Starting LLM enrichment with {OLLAMA_MODEL}...")

    # Combine all fields to check what's missing
    all_data = {**structured, **unstructured}
    missing  = [k for k, v in all_data.items() if not v]

    if not missing:
        print(f"  [OLLAMA] All fields already extracted — skipping LLM call.")
        return structured, unstructured

    print(f"  [OLLAMA] Missing fields to enrich: {missing}")

    # Build and send prompt
    prompt = _build_prompt(text, all_data)
    if not prompt:
        return structured, unstructured

    raw_response = _call_ollama(prompt)
    if not raw_response:
        print(f"  [OLLAMA] Empty response — returning rule-based data only.")
        return structured, unstructured

    print(f"  [OLLAMA] Response received ({len(raw_response)} chars)")

    # Parse response
    llm_data = _parse_response(raw_response)
    if not llm_data:
        return structured, unstructured

    # Merge LLM data — only fill in missing fields, never overwrite existing
    enriched_s = dict(structured)
    enriched_u = dict(unstructured)

    filled = []
    for field, value in llm_data.items():
        if not value or str(value).strip().lower() in ("null", "none", "n/a", ""):
            continue

        if field in enriched_s and not enriched_s[field]:
            enriched_s[field] = str(value).strip()
            filled.append(field)
        elif field in enriched_u and not enriched_u[field]:
            enriched_u[field] = str(value).strip()
            filled.append(field)

    if filled:
        print(f"  [OLLAMA] Enriched fields: {filled}")
    else:
        print(f"  [OLLAMA] No new fields filled by LLM.")

    return enriched_s, enriched_u
