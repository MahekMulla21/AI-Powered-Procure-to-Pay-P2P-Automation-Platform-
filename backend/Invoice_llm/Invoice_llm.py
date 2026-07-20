# Invoice_llm.py
import sys
from pathlib import Path
import json
import urllib.request
import urllib.error

from Invoice_config.Invoice_config import (
    OLLAMA_API_URL,
    OLLAMA_API_KEY,
    OLLAMA_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SEC,
    LLM_SYSTEM_PROMPT,
)

# Derive the Ollama base URL from the API URL for health checks
# e.g. "http://localhost:11434/v1/chat/completions" → "http://localhost:11434"
_OLLAMA_BASE_URL = OLLAMA_API_URL.split("/v1/")[0]


# ── Health check ─────────────────────────────────────────────────

def check_ollama_running() -> bool:
    """
    Ping the Ollama server. Returns True if reachable, False otherwise.
    Called by msa_main.py before starting the pipeline so the user
    gets a clear error instead of a timeout on every field.
    """
    try:
        with urllib.request.urlopen(f"{_OLLAMA_BASE_URL}/api/tags", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def check_model_available() -> bool:
    """
    Check whether OLLAMA_MODEL is already pulled on this machine.
    Returns True if found, False if not pulled yet.
    """
    try:
        with urllib.request.urlopen(f"{_OLLAMA_BASE_URL}/api/tags", timeout=5) as resp:
            data   = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", [])]
            # Ollama stores names like "llama3:latest" — check prefix match
            return any(OLLAMA_MODEL in m for m in models)
    except Exception:
        return False


# ── Core LLM call ────────────────────────────────────────────────

def call_llm(prompt: str, system: str = LLM_SYSTEM_PROMPT) -> str:
    """
    Send a prompt to the local Ollama llama3 endpoint and return the reply.

    Args:
        prompt  : User-turn message containing the extraction task + context.
        system  : System-turn message defining the assistant's role.

    Returns:
        The assistant's text reply, or a clear error string.
    """
    payload = json.dumps({
        "model"      : OLLAMA_MODEL,
        "messages"   : [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "temperature": LLM_TEMPERATURE,
        "stream"     : False,           # always get a single complete response
    }).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_API_URL,
        data    = payload,
        method  = "POST",
        headers = {
            "Content-Type" : "application/json",
            "Authorization": f"Bearer {OLLAMA_API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT_SEC) as response:
            raw  = response.read().decode("utf-8")
            data = json.loads(raw)

            # ── Parse response (OpenAI-compatible format) ─────────
            # Ollama /v1/chat/completions always returns this shape:
            # {"choices": [{"message": {"content": "..."}}]}
            content = (
                data
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if content:
                return content

            # Fallback: some Ollama builds return top-level "message"
            fallback = data.get("message", {}).get("content", "").strip()
            return fallback if fallback else "[LLM ERROR] Empty response from model."

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return f"[LLM HTTP ERROR {exc.code}] {body}"

    except urllib.error.URLError as exc:
        return (
            f"[LLM CONNECTION ERROR] Cannot reach Ollama at {_OLLAMA_BASE_URL}.\n"
            f"  → Make sure Ollama is running:  ollama serve\n"
            f"  → And the model is pulled:      ollama pull {OLLAMA_MODEL}\n"
            f"  → Raw error: {exc.reason}"
        )

    except json.JSONDecodeError as exc:
        return f"[LLM PARSE ERROR] Could not parse JSON response: {exc}"

    except Exception as exc:
        return f"[LLM ERROR] {exc}"


# ── Prompt builders ───────────────────────────────────────────────

def build_extraction_prompt(context: str, llm_hint: str) -> str:
    """
    Construct a structured extraction prompt.

    Args:
        context  : Relevant text snippet(s) retrieved via anchor or FAISS.
        llm_hint : Field-specific instruction from the field definition dict.

    Returns:
        Formatted prompt string ready to pass to call_llm().
    """
    return (
        f"Invoice text context:\n"
        f"---\n{context}\n---\n\n"
        f"Task: {llm_hint}\n"
        "Respond with ONLY the extracted value, nothing else. "
        "If the value cannot be found in the context, reply exactly: NOT FOUND"
    )


def build_unstructured_prompt(context: str, llm_hint: str) -> str:
    """
    Construct a narrative-generation prompt for unstructured fields.

    Args:
        context  : Top-k FAISS chunks concatenated as a single string.
        llm_hint : Field-specific narrative instruction.

    Returns:
        Formatted prompt string ready to pass to call_llm().
    """
    return (
        f"Invoice text context:\n"
        f"---\n{context}\n---\n\n"
        f"Task: {llm_hint}"
    )
