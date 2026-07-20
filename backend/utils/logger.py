"""
utils/logger.py
===============
Centralized enterprise-grade structured logger for the invoice pipeline.

Usage:
    from utils.logger import get_logger, log_exception

    logger = get_logger("invoice_main")
    logger.info("Processing file | file_id=%s | invoice=%s", file_id, inv_no)
    log_exception(logger, "Stage failed", exc, file_id=file_id)

Log format (structured JSON-style on file, readable on console):
    2026-05-13 22:10:01 | INFO  | invoice_main       | [file_id=42] Processing file ...
    2026-05-13 22:10:05 | ERROR | utils.ollama_client | [file_id=42] HTTP 403 Forbidden ...

Rotating file: logs/pipeline.log → 10 MB × 5 backups
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# ── Log directory ──────────────────────────────────────────────────────────────
_BACKEND = Path(__file__).resolve().parent.parent   # backend/
_LOG_DIR = _BACKEND / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "pipeline.log"

# ── Formats ────────────────────────────────────────────────────────────────────
_FILE_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
)
_CONSOLE_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── Root handler setup (run once) ──────────────────────────────────────────────
_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    if root.handlers:
        # Already configured externally (e.g. uvicorn) — just add file handler
        pass
    else:
        root.setLevel(logging.DEBUG)

    # ── Rotating file handler ──────────────────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        filename    = str(_LOG_FILE),
        maxBytes    = 10 * 1024 * 1024,   # 10 MB
        backupCount = 5,
        encoding    = "utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, _DATE_FORMAT))

    # ── Console handler (stdout, UTF-8 safe) ──────────────────────────────
    console_handler = logging.StreamHandler(
        stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8",
                    errors="replace", closefd=False)
        if hasattr(sys.stdout, "fileno") else sys.stdout
    )
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT, _DATE_FORMAT))

    # Only add to root if not already there
    existing_types = {type(h) for h in root.handlers}
    if logging.handlers.RotatingFileHandler not in existing_types:
        root.addHandler(file_handler)
    if logging.StreamHandler not in existing_types:
        root.addHandler(console_handler)

    _configured = True


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def get_logger(module_name: str) -> logging.Logger:
    """
    Return a named logger.  Call once per module at the top level:

        logger = get_logger("invoice_main")
    """
    _configure_root()
    return logging.getLogger(module_name)


def log_exception(
    logger:  logging.Logger,
    message: str,
    exc:     Exception,
    level:   int = logging.ERROR,
    **context,
) -> None:
    """
    Log an exception with full traceback + structured key=value context.

    Example:
        log_exception(logger, "LLM extraction failed", exc,
                      file_id=42, stage="llm_extraction")
    """
    ctx_str = " | ".join(f"{k}={v}" for k, v in context.items())
    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb_str   = "".join(tb_lines).strip()

    full_msg = (
        f"{message}"
        + (f" | {ctx_str}" if ctx_str else "")
        + f"\n  TRACEBACK:\n{_indent(tb_str, 4)}"
    )
    logger.log(level, full_msg)


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line for line in text.splitlines())
