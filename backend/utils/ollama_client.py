"""
utils/ollama_client.py
======================
Production-grade shared Ollama HTTP client.
Used by ALL pipeline modules (Invoice, MSA, PO, PR, SOW, Decision Engine).

Features:
  - Authorization: Bearer header (fixes 403 Forbidden)
  - Exponential-backoff retry (3 attempts: 2s, 4s, 8s)
  - Separate timeout vs connection error handling
  - Health-check / ping function
  - Never raises — always returns safe fallback string
  - Structured logging on every failure
"""

from __future__ import annotations

import json
import logging
import time
import os
import sys
from typing import Optional
from pathlib import Path

import requests
from requests.exceptions import Timeout, ConnectionError, HTTPError

# ── Resolve settings path ──────────────────────────────────────────────────────
_BACKEND = Path(__file__).resolve().parent.parent   # backend/
_INV_CONFIG = _BACKEND / "Invoice_config"
if str(_INV_CONFIG.parent) not in sys.path:
    sys.path.insert(0, str(_INV_CONFIG.parent))

# ── Load configuration ─────────────────────────────────────────────────────────
# Primary: Invoice_settings.py (has the remote URL + API key)
# Override any value with environment variables for 12-factor compliance.
try:
    from Invoice_config.Invoice_settings import (
        API_URL   as _DEFAULT_API_URL,
        API_KEY   as _DEFAULT_API_KEY,
        MODEL_NAME as _DEFAULT_MODEL,
    )
except ImportError:
    _DEFAULT_API_URL = "http://10.1.1.219:8080/ollama/api/generate"
    _DEFAULT_API_KEY = ""
    _DEFAULT_MODEL   = "llama3"

OLLAMA_API_URL: str = os.environ.get("OLLAMA_API_URL", _DEFAULT_API_URL)
OLLAMA_API_KEY: str = os.environ.get("OLLAMA_API_KEY", _DEFAULT_API_KEY)
OLLAMA_MODEL:   str = os.environ.get("OLLAMA_MODEL",   _DEFAULT_MODEL)

# ── Retry / timeout settings ────────────────────────────────────────────────────
_MAX_RETRIES:   int   = 1
_RETRY_DELAYS:  tuple = (2, 4, 8)          # seconds between attempts
_REQUEST_TIMEOUT: int = 180                 # seconds per attempt

logger = logging.getLogger("utils.ollama_client")


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
def ping_ollama(
    url:     str = OLLAMA_API_URL,
    api_key: str = OLLAMA_API_KEY,
    timeout: int = 8,
) -> dict:
    """
    Test connectivity to the Ollama server.

    Returns:
        {"reachable": True/False, "url": url, "error": None | str}
    """
    # Derive a health-check URL from the generate URL.
    # For Ollama native:  http://host:port/ollama/api/generate
    #                  →  http://host:port/ollama/api/tags
    # For OpenAI-compat: http://host:port/v1/chat/completions
    #                  →  http://host:port/  (basic reachability)
    try:
        if "/api/generate" in url:
            health_url = url.replace("/api/generate", "/api/tags")
        elif "/v1/chat" in url:
            health_url = url.split("/v1/")[0] + "/api/tags"
        else:
            health_url = url

        headers = _build_headers(api_key)
        resp = requests.get(health_url, headers=headers, timeout=timeout)
        reachable = resp.status_code in (200, 401)   # 401 = auth issue, server IS up

        if resp.status_code == 403:
            return {
                "reachable": False,
                "url":       health_url,
                "error":     f"HTTP 403 Forbidden — API key may be wrong or missing. "
                             f"Current key starts with: {api_key[:8] if api_key else '(empty)'}",
            }

        return {
            "reachable": reachable,
            "url":       health_url,
            "error":     None if reachable else f"HTTP {resp.status_code}",
        }

    except ConnectionError as exc:
        return {
            "reachable": False,
            "url":       url,
            "error":     f"Connection refused — is Ollama running? ({exc})",
        }
    except Timeout:
        return {
            "reachable": False,
            "url":       url,
            "error":     f"Health check timed out after {timeout}s",
        }
    except Exception as exc:
        return {
            "reachable": False,
            "url":       url,
            "error":     str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _build_headers(api_key: str) -> dict:
    """Build HTTP headers with Authorization if key is provided."""
    headers = {"Content-Type": "application/json"}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    return headers


def _build_payload(
    prompt: str,
    model:  str,
    temperature: float = 0.0,
    num_predict: int   = 2048,
    stream: bool       = False,
) -> dict:
    """Build the Ollama /api/generate payload."""
    return {
        "model":   model,
        "prompt":  prompt,
        "stream":  stream,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }


def _extract_text(response_json: dict) -> str:
    """
    Extract the generated text from an Ollama API response.
    Handles both:
      - Native Ollama:       {"response": "..."}
      - OpenAI-compatible:   {"choices": [{"message": {"content": "..."}}]}
    """
    # Native Ollama format
    if "response" in response_json:
        return response_json["response"].strip()

    # OpenAI-compatible format
    choices = response_json.get("choices", [])
    if choices and isinstance(choices, list):
        msg = choices[0].get("message", {})
        content = msg.get("content", "").strip()
        if content:
            return content

    # Some Ollama versions return top-level "message"
    fallback = response_json.get("message", {})
    if isinstance(fallback, dict):
        return fallback.get("content", "").strip()

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PUBLIC FUNCTION
# ─────────────────────────────────────────────────────────────────────────────
def call_llm(
    prompt:      str,
    model:       str   = OLLAMA_MODEL,
    url:         str   = OLLAMA_API_URL,
    api_key:     str   = OLLAMA_API_KEY,
    temperature: float = 0.0,
    num_predict: int   = 2048,
    timeout:     int   = _REQUEST_TIMEOUT,
    max_retries: int   = _MAX_RETRIES,
    file_id:     Optional[int] = None,
) -> str:
    """
    Send a prompt to the Ollama HTTP API with retry + auth.

    Args:
        prompt:      The text prompt to send.
        model:       Ollama model name (default: from settings).
        url:         Ollama API endpoint (default: from settings).
        api_key:     Bearer token (default: from settings).
        temperature: Sampling temperature (default 0 = deterministic).
        num_predict: Max tokens to generate.
        timeout:     Per-request timeout in seconds.
        max_retries: Number of attempts before giving up.
        file_id:     Optional file_id for structured logging context.

    Returns:
        Generated text string, or "{}" on complete failure (never raises).
    """
    ctx = f"file_id={file_id}" if file_id else "no file_id"
    headers = _build_headers(api_key)
    payload  = _build_payload(prompt, model, temperature, num_predict)

    last_error: str = "unknown"

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "[OllamaClient] Attempt %d/%d | model=%s | url=%s | %s",
                attempt, max_retries, model, url, ctx,
            )

            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)

            # ── Handle HTTP errors explicitly ─────────────────────────────
            if resp.status_code == 403:
                logger.error(
                    "[OllamaClient] 403 Forbidden on attempt %d | url=%s | "
                    "key_prefix=%s | hint: Check API key / proxy auth | %s",
                    attempt, url,
                    api_key[:8] if api_key else "(empty)",
                    ctx,
                )
                last_error = f"HTTP 403 Forbidden — API key rejected by {url}"
                break   # 403 is auth — no point retrying

            resp.raise_for_status()

            # ── Parse response ────────────────────────────────────────────
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.error(
                    "[OllamaClient] JSON parse failed on attempt %d: %s | %s",
                    attempt, json_err, ctx,
                )
                last_error = f"JSON parse error: {json_err}"
                _wait_if_retrying(attempt, max_retries)
                continue

            text = _extract_text(data)
            if not text:
                logger.warning(
                    "[OllamaClient] Empty response on attempt %d | %s", attempt, ctx
                )
                last_error = "empty response from model"
                _wait_if_retrying(attempt, max_retries)
                continue

            logger.info(
                "[OllamaClient] Success on attempt %d | response_len=%d | %s",
                attempt, len(text), ctx,
            )
            return text

        except Timeout:
            last_error = f"timeout after {timeout}s"
            logger.warning(
                "[OllamaClient] Timeout on attempt %d/%d | %s", attempt, max_retries, ctx
            )
            _wait_if_retrying(attempt, max_retries)

        except ConnectionError as exc:
            last_error = f"connection refused: {exc}"
            logger.warning(
                "[OllamaClient] Connection error on attempt %d/%d: %s | %s",
                attempt, max_retries, exc, ctx,
            )
            _wait_if_retrying(attempt, max_retries)

        except HTTPError as exc:
            last_error = f"HTTP {exc.response.status_code}: {exc}"
            logger.error(
                "[OllamaClient] HTTP error on attempt %d/%d: %s | %s",
                attempt, max_retries, exc, ctx,
            )
            _wait_if_retrying(attempt, max_retries)

        except Exception as exc:
            last_error = str(exc)
            logger.error(
                "[OllamaClient] Unexpected error on attempt %d/%d: %s | %s",
                attempt, max_retries, exc, ctx,
            )
            _wait_if_retrying(attempt, max_retries)

    # All retries exhausted
    logger.error(
        "[OllamaClient] All %d attempts failed | last_error=%s | %s",
        max_retries, last_error, ctx,
    )
    return "{}"


def _wait_if_retrying(attempt: int, max_retries: int) -> None:
    """Sleep between retries only if there are more attempts left."""
    if attempt < max_retries:
        delay = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
        logger.info("[OllamaClient] Waiting %ds before retry...", delay)
        time.sleep(delay)
