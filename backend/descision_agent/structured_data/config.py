# ─────────────────────────────────────────────────────────────
# decision_agent/config.py
# ─────────────────────────────────────────────────────────────

import os
from pathlib import Path

# ── PostgreSQL — your clrvw_db ────────────────────────────────
DB_CONFIG = {
    "host":     "10.1.1.53",
    "database": "clrvw_db",
    "user":     "postgres",
    "password": "postgres",
    "port":     "5432",
}

# ── Ollama LLM ────────────────────────────────────────────────
# Load from environment variables first (12-factor), fall back to
# Invoice_settings.py so there is one source of truth for the key.
LLM_API_URL: str = os.environ.get("OLLAMA_API_URL", "http://10.1.1.219:8080/ollama/api/generate")
LLM_MODEL:   str = os.environ.get("OLLAMA_MODEL",   "llama3")
LLM_TIMEOUT: int = int(os.environ.get("OLLAMA_TIMEOUT", "90"))

# API key: env var → Invoice_settings → empty string
_raw_key: str = os.environ.get("OLLAMA_API_KEY", "")
if not _raw_key:
    try:
        # Walk up to backend/ and import Invoice_settings
        _backend = Path(__file__).resolve().parent.parent.parent  # backend/
        import sys
        if str(_backend) not in sys.path:
            sys.path.insert(0, str(_backend))
        from Invoice_config.Invoice_settings import API_KEY as _settings_key
        _raw_key = _settings_key or ""
    except Exception:
        _raw_key = ""

LLM_API_KEY: str = _raw_key

# ── Log directory ─────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

