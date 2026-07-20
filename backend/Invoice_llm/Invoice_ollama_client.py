"""
Invoice_ollama_client.py
========================
Thin wrapper around the shared utils.ollama_client.
Delegates ALL HTTP work (auth, retry, timeout) to the shared client.

Root-cause fix: the bare requests.post() with no Authorization header
caused HTTP 403 Forbidden. The shared client now sends:
    Authorization: Bearer <API_KEY>
and retries up to 3 times with exponential backoff.
"""

import logging
import sys
from pathlib import Path

# ── Ensure backend/ is on path so utils package is importable ─────────────────
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from utils.ollama_client import call_llm as _shared_call_llm, ping_ollama  # noqa: E402
from Invoice_config.Invoice_settings import MODEL_NAME, API_URL, API_KEY   # noqa: E402

logger = logging.getLogger("Invoice_ollama_client")


def call_llm(prompt: str, file_id=None) -> str:
    """
    Send prompt to Ollama HTTP API.

    Auth:    Authorization: Bearer <API_KEY>  (fixes 403 Forbidden)
    Retry:   3 attempts with exponential backoff (2s, 4s, 8s)
    Timeout: 120 seconds per attempt
    Fallback: returns '{}' on any failure — never raises

    Args:
        prompt:  The text prompt to send.
        file_id: Optional file_id for log context.

    Returns:
        Raw text response from the LLM, or '{}' on failure.
    """
    logger.info(
        "[Invoice_LLM] Calling Ollama | url=%s | model=%s | file_id=%s",
        API_URL, MODEL_NAME, file_id,
    )

    result = _shared_call_llm(
        prompt    = prompt,
        model     = MODEL_NAME,
        url       = API_URL,
        api_key   = API_KEY,
        file_id   = file_id,
    )

    if result == "{}":
        logger.warning(
            "[Invoice_LLM] LLM returned empty/fallback — rule-based data will be used | file_id=%s",
            file_id,
        )
    else:
        logger.info(
            "[Invoice_LLM] LLM response received | len=%d | file_id=%s",
            len(result), file_id,
        )

    return result


def health_check() -> dict:
    """
    Ping the Ollama server to verify connectivity.

    Returns:
        {"reachable": bool, "url": str, "error": str | None}
    """
    return ping_ollama(url=API_URL, api_key=API_KEY)