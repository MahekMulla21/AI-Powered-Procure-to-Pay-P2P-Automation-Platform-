"""
pipeline_status.py — In-memory store for pipeline results.
Kept separate so both app.py and main.py can import without circular deps.
"""
import threading
from typing import Optional

_lock = threading.Lock()

# { file_id: { "state": "pending"|"running"|"done"|"failed", "pipeline": str, "status": str, "doc_id": str, "action": str, "error": str } }
_store: dict = {}


def set_running(file_id: int, pipeline: str):
    with _lock:
        _store[file_id] = {"state": "running", "pipeline": pipeline}


def set_done(file_id: int, pipeline: str, match_status: str, doc_id: str, action: str):
    """
    match_status : "NEW" | "DUPLICATE" | "REVIEW_REQUIRED"
    doc_id       : e.g. "MSA-TCS-STC-2024-001"
    action       : human-readable e.g. "Inserted new record" / "Deactivated old + inserted" / "Skipped (duplicate)"
    """
    with _lock:
        _store[file_id] = {
            "state":        "done",
            "pipeline":     pipeline,
            "match_status": match_status,
            "doc_id":       doc_id,
            "action":       action,
        }


def set_failed(file_id: int, pipeline: str, error: str):
    with _lock:
        _store[file_id] = {
            "state":    "failed",
            "pipeline": pipeline,
            "error":    error,
        }


def get(file_id: int) -> Optional[dict]:
    with _lock:
        return _store.get(file_id)