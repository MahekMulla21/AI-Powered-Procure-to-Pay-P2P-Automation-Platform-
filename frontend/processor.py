"""
processor.py — Filename cleaner and document type detector
"""

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def clean_filename(file_name: str) -> str:
    name = os.path.splitext(file_name)[0]
    name = re.sub(r"[_\-]+", " ", name)
    name = re.sub(r"\b\d+\b", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name.lower()


def detect_document_type(clean_name: str) -> str:
    patterns = {
        "msa":     ["msa", "master service agreement", "service agreement"],
        "sow":     ["sow", "statement of work"],
        "po":      ["po", "purchase order"],
        "pr":      ["pr", "purchase request", "purchase requisition"],
        "invoice": ["invoice", "inv", "bill"]
    }

    for doc_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in clean_name:
                return doc_type

    return "unknown"