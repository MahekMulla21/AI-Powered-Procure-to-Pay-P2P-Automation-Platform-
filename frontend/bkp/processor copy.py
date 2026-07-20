"""
processor.py — Smart Multi-Pipeline Router
Scans input/success/, detects document type, and routes each file
to the correct backend pipeline automatically.

Supported:
- msa_main.py
- sow_main.py
- po_main.py
- pr_main.py
- invoice_main.py

Usage:
    python processor.py
"""

import os
import re
import sys
import subprocess

# ── Windows-safe UTF-8 console output ───────────────────────────────────────
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── Base paths ───────────────────────────────────────────────────────────────
BASE_DIR = os.getcwd()

# frontend/input/success
INPUT_DIR = os.path.join(
    BASE_DIR,
    "input",
    "success"
)

# backend folder
BACKEND_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "backend")
)


# ── File name cleaner ────────────────────────────────────────────────────────
def clean_filename(file_name: str) -> str:
    """
    Cleans dynamic uploaded filenames:
    Example:
    1777293947_SOW_TCS_STC_DataMigration_2024_20260427_181547.docx
    → sow tcs stc datamigration
    """
    name = os.path.splitext(file_name)[0]

    # Replace separators
    name = re.sub(r"[_\-]+", " ", name)

    # Remove numbers
    name = re.sub(r"\b\d+\b", " ", name)

    # Remove extra spaces
    name = re.sub(r"\s+", " ", name).strip()

    return name.lower()


# ── Smart detector ───────────────────────────────────────────────────────────
def detect_document_type(clean_name: str) -> str:
    patterns = {
        "msa": [
            "msa",
            "master service agreement",
            "service agreement"
        ],
        "sow": [
            "sow",
            "statement of work"
        ],
        "po": [
            "po",
            "purchase order"
        ],
        "pr": [
            "pr",
            "purchase request",
            "purchase requisition"
        ],
        "invoice": [
            "invoice",
            "inv",
            "bill"
        ]
    }

    for doc_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in clean_name:
                return doc_type

    return "unknown"


# ── Generic pipeline runner ──────────────────────────────────────────────────
def run_pipeline(script_name: str, file_path: str, file_name: str, label: str, file_id=None):
    script_path = os.path.join(BACKEND_DIR, script_name)

    if not os.path.exists(script_path):
        print(f"[ERROR] {label} pipeline not found: {script_path}")
        return

    print(f"[{label}] Processing: {file_name}")
    print(f"[FILE PATH] {file_path}")
    print(f"[START] Running: {script_path}")

    try:
        cmd = ["python", script_path, file_path]
        if file_id is not None:
            cmd.append(str(file_id))          # ← forwards file_id to msa_main.py

        result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        check=True
    )

        print(f"[SUCCESS] {label} completed successfully")

        if result.stdout:
            print(f"[OUTPUT]\n{result.stdout}")

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {label} processing failed with exit code {e.returncode}")
        print(f"[STDERR]\n{e.stderr}")   # ← now you'll see the real error
        print(f"[STDOUT]\n{e.stdout}")

# ── Handlers ─────────────────────────────────────────────────────────────────
def process_msa(file_path: str, file_name: str, file_id=None):
    run_pipeline("msa_main.py", file_path, file_name, "MSA", file_id)

def process_sow(file_path: str, file_name: str, file_id=None):
    run_pipeline("sow_main.py", file_path, file_name, "SOW", file_id)

def process_po(file_path: str, file_name: str, file_id=None):
    run_pipeline("po_main.py", file_path, file_name, "PO", file_id)

def process_pr(file_path: str, file_name: str, file_id=None):
    run_pipeline("pr_main.py", file_path, file_name, "PR", file_id)

def process_invoice(file_path: str, file_name: str, file_id=None):
    run_pipeline("invoice_main.py", file_path, file_name, "INVOICE", file_id)


# ── Route map ────────────────────────────────────────────────────────────────
ROUTE_MAP = {
    "msa": process_msa,
    "sow": process_sow,
    "po": process_po,
    "pr": process_pr,
    "invoice": process_invoice
}


# ── Core router ──────────────────────────────────────────────────────────────
def route_file(file_name: str, full_file_path: str = None, file_id=None):

    file_path = full_file_path if full_file_path else os.path.join(INPUT_DIR, file_name)

    cleaned_name = clean_filename(file_name)

    doc_type = detect_document_type(cleaned_name)

    print(f"\n[FILE] Original File : {file_name}")
    print(f"[CLEANED] Cleaned Name : {cleaned_name}")
    print(f"[DETECTED] Type : {doc_type.upper()}")

    handler = ROUTE_MAP.get(doc_type)

    if handler:
        handler(file_path, file_name, file_id)
    else:
        print(f"[SKIP] No handler matched for: {file_name}")


# ── Main processor ───────────────────────────────────────────────────────────
def process_all():
    if not os.path.exists(INPUT_DIR):
        print(f"[ERROR] Input folder not found: {INPUT_DIR}")
        sys.exit(1)

    if not os.path.exists(BACKEND_DIR):
        print(f"[ERROR] Backend folder not found: {BACKEND_DIR}")
        sys.exit(1)

    files = [
        f for f in os.listdir(INPUT_DIR)
        if not f.startswith(".")
        and os.path.isfile(os.path.join(INPUT_DIR, f))
    ]

    if not files:
        print("[INFO] No files found in input/success/")
        return

    print(f"[INFO] Found {len(files)} file(s) in input/success/\n")

    for file_name in files:
        route_file(file_name)

    print("\n[SUCCESS] All pipelines completed.")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        uploaded_file_path = sys.argv[1]

        if not os.path.exists(uploaded_file_path):
            print(f"[ERROR] File not found: {uploaded_file_path}")
            sys.exit(1)

        uploaded_file_name = os.path.basename(uploaded_file_path)
        file_id = int(sys.argv[2]) if len(sys.argv) >= 3 else None  # ← read file_id

        print("[INFO] Processing single uploaded file...")
        route_file(uploaded_file_name, uploaded_file_path, file_id)  # ← pass it
    else:
        print("[INFO] No file path passed. Processing all files...")
        process_all()