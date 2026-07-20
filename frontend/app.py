# =========================
# app.py — MERGED (ClearView + AI Document Agent)
# Combines:
#   - Original self-contained pipeline (DQ → OCR → classify → extract → insert)
#   - ClearView FastAPI backend (background tasks, pipeline_status, invoice decision)
# =========================

import os
import shutil
import uuid
import traceback
import json
import logging
import time
from datetime import datetime
from pathlib import Path
import sys

# ─── Path setup ───────────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent
BACKEND_DIR  = FRONTEND_DIR.parent / "backend"

for p in [str(FRONTEND_DIR), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ─── FastAPI ──────────────────────────────────────────────────────────────────
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─── Local imports (original pipeline) ───────────────────────────────────────
from dq_agent import validate_file, move_file
from db import get_connection
from ocr_engine import extract_text
from doc_classifier import classify_document
from llm_extractor import extract_fields

from db_inserter import (
    insert_msa_dataset,
    insert_sow_dataset,
    insert_invoice_dataset,
    insert_pr_dataset,
    insert_po_dataset,
)

# ─── ClearView pipeline imports (optional; guarded) ───────────────────────────
try:
    from processor import clean_filename, detect_document_type
    from main import (
        run_msa_pipeline,
        run_invoice_pipeline,
        run_sow_pipeline,
        run_po_pipeline,
        run_pr_pipeline,
    )

    DECISION_AGENT_DIR = BACKEND_DIR / "descision_agent"
    for p in [
        str(DECISION_AGENT_DIR),
        str(DECISION_AGENT_DIR / "structured_data"),
        str(DECISION_AGENT_DIR / "invoice_agent"),   # NEW
    ]:
        if p not in sys.path:
            sys.path.insert(0, p)


    from db import save_file_record, save_validation_logs
    import pipeline_status as ps

    CLEARVIEW_AVAILABLE = True
except ImportError:
    CLEARVIEW_AVAILABLE = False

# ─── UTF-8 fix ────────────────────────────────────────────────────────────────
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# =============================================================================
# APP
# =============================================================================
app = FastAPI(title="ClearView Document Pipeline")

# =============================================================================
# CORS
# =============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*",  # fallback for direct API usage
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# DIRECTORIES
# =============================================================================
BASE_DIR  = os.getcwd()
INPUT_DIR = os.path.join(BASE_DIR, "input")
TEMP_DIR  = os.path.join(BASE_DIR, "summary")
LOG_DIR   = os.path.join(BASE_DIR, "logs")

for directory in [INPUT_DIR, TEMP_DIR, LOG_DIR]:
    os.makedirs(directory, exist_ok=True)

# =============================================================================
# LOGGING
# =============================================================================
log_filename = os.path.join(
    LOG_DIR,
    f"app_log_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("app")
SEP = "-" * 60

# =============================================================================
# INVOICE DECISION STORE  (in-memory)
# =============================================================================
_invoice_decisions: dict = {}


# =============================================================================
# UTILITIES
# =============================================================================

def safe_value(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    val = str(val).strip()
    if val.lower() in ["", "na", "null", "none"]:
        return None
    return val


def detect_field_type(field_name, value):
    if value is None:
        return "UNSTRUCTURED"
    if isinstance(value, (dict, list)):
        return "UNSTRUCTURED"
    value = str(value).strip()
    structured_fields = [
        "invoice_number", "invoice_date", "po_number", "po_date",
        "msa_number", "sow_number", "pr_number", "amount",
        "currency", "tax", "quantity", "unit_price",
        "start_date", "end_date", "vendor_name", "client_name"
    ]
    if field_name.lower() in structured_fields:
        return "STRUCTURED"
    if (
        value.replace(".", "", 1).isdigit()
        or "/" in value
        or "-" in value
    ):
        return "STRUCTURED"
    return "UNSTRUCTURED"


def get_field_status(value):
    if value is None:
        return "Missing"
    if isinstance(value, (dict, list)):
        return "Missing" if len(value) == 0 else "Valid"
    value = str(value).strip().lower()
    if value in ["", "na", "null", "none", "[]", "{}"]:
        return "Missing"
    return "Valid"


# =============================================================================
# DB HELPERS
# =============================================================================

def insert_extracted(file_id, doc_type, data, table):
    conn = get_connection()
    cur = conn.cursor()
    try:
        for field, value in data.items():
            status = get_field_status(value)
            field_type = detect_field_type(field, value)
            cur.execute(f"""
                INSERT INTO {table}
                (file_id, document_type, field_name, field_value, field_status, field_type)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (file_id, doc_type, field, safe_value(value), status, field_type))
        conn.commit()
        print(f"✅ {table} inserted")
    except Exception as e:
        conn.rollback()
        print(f"❌ {table} insert error:", e)
    finally:
        cur.close()
        conn.close()


def save_file(file_name, path, file_type, size, status, reason, mode, doc_type):
    conn = get_connection()
    cur = conn.cursor()
    fid = None
    try:
        if mode == "DATA":
            cur.execute("""
                INSERT INTO files (file_name, file_path, file_type, file_size, status, reason)
                VALUES (%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (file_name, path, file_type, size, status, reason))
        else:
            cur.execute("""
                INSERT INTO files_dataset (file_name, file_path, file_type, file_size, status, reason, doc_type)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (file_name, path, file_type, size, status, reason, doc_type))
        fid = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("❌ File insert error:", e)
    finally:
        cur.close()
        conn.close()
    return fid


def save_main_table(doc_type, data, file_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        print("🔥 FINAL DATA BEFORE INSERT:", data)

        if doc_type == "PO":
            cur.execute("""
                INSERT INTO po_data (
                    po_number, po_date, vendor_name, client_name,
                    payment_terms, delivery_terms, currency,
                    total_amount, start_date, end_date,
                    reference_sow, reference_msa, status,
                    quantity, unit_price, tax, tax_breakup,
                    service_code, delivery_location,
                    grn_indicator, po_status,
                    description_of_goods_and_services, file_id
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s)
            """, (
                data.get("po_number"),
                data.get("po_date"),
                data.get("vendor_name"),
                data.get("client_name"),
                data.get("payment_terms"),
                data.get("delivery_terms"),
                data.get("currency"),
                data.get("total_amount"),
                data.get("start_date"),
                data.get("end_date"),
                data.get("reference_sow"),
                data.get("reference_msa"),
                data.get("po_status"),
                data.get("quantity"),
                data.get("unit_price"),
                data.get("tax"),
                safe_value(data.get("tax_breakup")),
                safe_value(data.get("service_code")),
                safe_value(data.get("delivery_location")),
                data.get("grn_indicator"),
                data.get("po_status"),
                safe_value(data.get("description_of_goods_and_services")),
                file_id
            ))

        elif doc_type == "MSA":
            cur.execute("""
                INSERT INTO msa_data (file_id, vendor_name, start_date, end_date)
                VALUES (%s,%s,%s,%s)
            """, (file_id, data.get("vendor_name"), data.get("start_date"), data.get("end_date")))

        elif doc_type == "SOW":
            cur.execute("""
                INSERT INTO sow_data (file_id, service_name, total_amount)
                VALUES (%s,%s,%s)
            """, (file_id, data.get("service_name"), data.get("total_amount")))

        elif doc_type == "INVOICE":
            cur.execute("""
                INSERT INTO invoice_data (file_id, vendor_name, invoice_number)
                VALUES (%s,%s,%s)
            """, (file_id, data.get("vendor_name"), data.get("invoice_number")))

        elif doc_type == "PR":
            cur.execute("""
                INSERT INTO pr_data (file_id, pr_number, vendor_name, total_amount)
                VALUES (%s,%s,%s,%s)
            """, (file_id, data.get("pr_number"), data.get("vendor_name"), data.get("total_amount")))

        conn.commit()
        print("✅ Main table inserted")

    except Exception as e:
        conn.rollback()
        print("❌ Main table insert error:", e)
    finally:
        cur.close()
        conn.close()


def get_data(table, file_table):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT d.*, f.file_name
            FROM {table} d
            LEFT JOIN {file_table} f ON d.file_id = f.id
            ORDER BY d.file_id DESC
        """)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return {"data": rows}
    except Exception as e:
        print("❌ get_data error:", e)
        return {"data": []}
    finally:
        cur.close()
        conn.close()


def get_dataset_data(dataset_table, doc_type):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT d.file_id, f.file_name, e.field_name, e.field_value, e.field_type, e.field_status
            FROM {dataset_table} d
            JOIN files_dataset f ON d.file_id = f.id
            JOIN extracted_dataset e ON d.file_id = e.file_id
            WHERE d.active_flag = 1 AND UPPER(e.document_type) = %s
            ORDER BY d.file_id DESC
        """, (doc_type.upper(),))
        rows = cur.fetchall()
        result = {}
        for (fid, fname, field, value, field_type, field_status) in rows:
            if fid not in result:
                result[fid] = {"file_id": fid, "file_name": fname}
            result[fid][field] = value
            result[fid][f"{field}_field_type"] = field_type
            result[fid][f"{field}_status"] = field_status
        return {"data": list(result.values())}
    except Exception as e:
        print("❌ dataset fetch error:", e)
        return {"data": []}
    finally:
        cur.close()
        conn.close()


# =============================================================================
# CLEARVIEW BACKGROUND PIPELINE RUNNER
# =============================================================================

def run_pipeline(file_path: str, file_id: int, doc_type: str):
    if not CLEARVIEW_AVAILABLE:
        logger.warning("[PIPELINE] ClearView modules not available; skipping background pipeline.")
        return
    pipeline_name = doc_type.upper()
    try:
        logger.info(SEP)
        logger.info(f"[PIPELINE START] file_id={file_id} | type={pipeline_name}")
        logger.info(SEP)

        ps.set_running(file_id, pipeline_name)
        start = time.time()

        if doc_type == "msa":
            result = run_msa_pipeline(file_path, file_id)
        elif doc_type == "sow":
            result = run_sow_pipeline(file_path, file_id)
        elif doc_type == "po":
            result = run_po_pipeline(file_path, file_id)
        elif doc_type == "pr":
            result = run_pr_pipeline(file_path, file_id)
        elif doc_type == "invoice":
            result = run_invoice_pipeline(file_path, file_id)
        else:
            ps.set_failed(file_id, pipeline_name, "Unknown document type")
            return

        elapsed = round(time.time() - start, 2)
        logger.info(f"[PIPELINE DONE] {pipeline_name} | time={elapsed}s")

        if result.get("status") == "success":
            ps.set_done(
                file_id=file_id,
                pipeline=pipeline_name,
                match_status=result.get("match_status", "UNKNOWN"),
                doc_id=result.get("doc_id", ""),
                action=result.get("action", "Completed"),
            )
        else:
            ps.set_failed(file_id, pipeline_name, result.get("error", "Pipeline failed"))

    except Exception as ex:
        logger.exception(f"[PIPELINE ERROR] file_id={file_id}")
        if CLEARVIEW_AVAILABLE:
            ps.set_failed(file_id, pipeline_name, str(ex))


def run_invoice_decision_pipeline(file_path: str, file_id: int):
    """
    Background task for invoice decision pipeline.
    Uses invoice_agent_runner instead of old invoice_decision_runner.
    """

    # IMPORTANT: ensure backend root is importable
    backend_root = str(BACKEND_DIR)

    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    # IMPORTANT: ensure descision_agent is importable
    decision_agent_path = str(BACKEND_DIR / "descision_agent")

    if decision_agent_path not in sys.path:
        sys.path.insert(0, decision_agent_path)

    _invoice_decisions[file_id] = {
        "state": "running",
        "file_id": file_id
    }

    try:
        logger.info(f"[INVOICE DECISION] START | file_id={file_id}")

        # NEW AGENT RUNNER
        from invoice_agent_runner import run as run_agent_decision

        result = run_agent_decision(file_path, file_id)

        _invoice_decisions[file_id] = {
            "state": "done",
            "file_id": file_id,
            "verdict": result.get("verdict", {}),
            "rag_context": result.get("rag_context", ""),
            "extraction": {
                "invoice_number": result.get("extraction", {}).get("invoice_number"),
                "status": result.get("extraction", {}).get("status"),

                "po_reference": result.get("extraction", {})
                    .get("structured", {})
                    .get("po_reference_number"),

                "msa_id": result.get("extraction", {})
                    .get("structured", {})
                    .get("msa_id"),

                "sow_id": result.get("extraction", {})
                    .get("structured", {})
                    .get("sow_id"),
            },
        }

        logger.info(
            f"[INVOICE DECISION DONE] "
            f"file_id={file_id} | "
            f"verdict={result.get('verdict', {}).get('verdict', '?')}"
        )

    except Exception as ex:
        logger.exception(f"[INVOICE DECISION ERROR] file_id={file_id}")

        _invoice_decisions[file_id] = {
            "state": "failed",
            "file_id": file_id,
            "error": str(ex),
            "traceback": traceback.format_exc(),
        }

# =============================================================================
# ROUTES — ROOT & HEALTH
# =============================================================================

@app.get("/")
def home():
    return {
        "status":  "running",
        "message": "ClearView Document Pipeline + AI Document Agent Running ✅"
    }


@app.get("/health")
def health():
    return {
        "status":    "running",
        "app":       "ClearView Document Pipeline",
        "pipelines": ["MSA", "SOW", "PO", "PR", "INVOICE"],
    }


@app.get("/health/ollama")
def ollama_health():
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            return {"status": "connected", "ollama": "running", "models": response.json()}
        return JSONResponse(status_code=500, content={"status": "failed", "message": "Ollama not responding"})
    except Exception as ex:
        return JSONResponse(status_code=500, content={"status": "failed", "error": str(ex)})


# =============================================================================
# ROUTE — SELF-CONTAINED UPLOAD  (original pipeline)
# POST /upload-file
# DQ → OCR → classify → extract → insert (synchronous, returns result directly)
# =============================================================================

@app.post("/upload-file")
async def upload_file_direct(
    file: UploadFile = File(...),
    mode: str = Form(...),
):
    try:
        print("🚀 Upload Started")
        mode = mode.upper()

        os.makedirs("uploads", exist_ok=True)
        path = f"uploads/{uuid.uuid4()}_{file.filename}"

        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate
        status, reason, _ = validate_file(path)

        # OCR
        text = extract_text(path)
        if not text:
            return {"success": False, "message": "OCR extraction failed"}

        # Classify
        doc_type = classify_document(text).upper()
        print("📄 Detected:", doc_type)

        # Save file record
        fid = save_file(
            file.filename,
            path,
            file.filename.split(".")[-1],
            os.path.getsize(path),
            status,
            reason,
            mode,
            doc_type,
        )
        if not fid:
            return {"success": False, "message": "File save failed"}

        # Extract
        data = extract_fields(text, doc_type)
        if not data or not any(data.values()):
            print("❌ Extraction failed")
            return {"success": False, "message": "Data extraction failed", "file": file.filename}

        # Persist
        if mode == "DATA":
            save_main_table(doc_type, data, fid)
            insert_extracted(fid, doc_type, data, "extracted_data")
        else:
            insert_extracted(fid, doc_type, data, "extracted_dataset")
            if doc_type == "MSA":
                insert_msa_dataset(data, fid)
            elif doc_type == "SOW":
                insert_sow_dataset(data, fid)
            elif doc_type == "INVOICE":
                insert_invoice_dataset(data, fid)
            elif doc_type == "PR":
                insert_pr_dataset(data, fid)
            elif doc_type == "PO":
                insert_po_dataset(data, fid)

        print("✅ Upload Completed")
        return {
            "success":  True,
            "message":  "Data extracted successfully",
            "file":     file.filename,
            "doc_type": doc_type,
            "file_id":  fid,
            "status":   status,
            "reason":   reason,
        }

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "message": str(e)}


# =============================================================================
# ROUTE — CLEARVIEW BACKGROUND UPLOAD
# POST /upload
# Validates → detects doc type → saves DB → runs pipeline in background
# =============================================================================

@app.post("/upload")
async def upload_file_background(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not CLEARVIEW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ClearView pipeline modules not available. Use /upload-file instead."
        )
    try:
        logger.info("[REQUEST] POST /upload")

        safe_name = "".join(
            c if c.isalnum() or c in "._-" else "_"
            for c in file.filename
        )
        temp_filename = f"{int(datetime.now().timestamp())}_{safe_name}"
        temp_file_path = os.path.join(TEMP_DIR, temp_filename)

        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"[TEMP SAVE] {temp_file_path}")

        status, reason, logs = validate_file(temp_file_path)
        logger.info(f"[VALIDATION] {status} | {reason}")

        final_path = move_file(temp_file_path, status)

        doc_type = detect_document_type(clean_filename(temp_filename))
        logger.info(f"[DOC TYPE] {doc_type}")

        file_id = save_file_record(
            file.filename,
            final_path,
            file.filename.split(".")[-1].lower(),
            os.path.getsize(final_path),
            status,
            reason,
            doc_type,
        )
        save_validation_logs(file_id, logs)
        logger.info(f"[DB SAVED] file_id={file_id}")

        if status != "VALID":
            return JSONResponse(status_code=400, content={"ok": False, "message": reason})

        ps.set_running(file_id, doc_type.upper())
        background_tasks.add_task(run_pipeline, final_path, file_id, doc_type)

        return {
            "ok":       True,
            "file_id":  file_id,
            "doc_type": doc_type,
            "message":  "Pipeline started successfully",
        }

    except Exception as ex:
        logger.exception("[UPLOAD ERROR]")
        raise HTTPException(status_code=500, detail=str(ex))


# =============================================================================
# ROUTE — PIPELINE STATUS
# GET /status/{file_id}
# =============================================================================

@app.get("/status/{file_id}")
async def get_status(file_id: int):
    if not CLEARVIEW_AVAILABLE:
        raise HTTPException(status_code=503, detail="ClearView pipeline not available.")
    entry = ps.get(file_id)
    if entry is None:
        return JSONResponse(status_code=404, content={"ok": False, "message": "No status found"})
    return {"ok": True, "file_id": file_id, **entry}


# =============================================================================
# ROUTE — INVOICE DECISION UPLOAD
# POST /upload-invoice
# =============================================================================

@app.post("/upload-invoice")
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    try:
        logger.info("[REQUEST] POST /upload-invoice")

        # if not file.filename.lower().endswith(".pdf"):
        #     raise HTTPException(status_code=400, detail="Only PDF invoices allowed")

        # allowed_extensions = [".pdf", ".doc", ".docx"]

        filename = file.filename.lower()
        allowed_extensions = [".pdf", ".doc", ".docx"]
        if not any(filename.endswith(ext) for ext in allowed_extensions):
            raise HTTPException(
                status_code=400,
                detail="Only PDF, DOC, and DOCX invoices allowed"
            )

        safe_name = "".join(
            c if c.isalnum() or c in "._-" else "_"
            for c in file.filename
        )
        temp_filename = f"{int(datetime.now().timestamp())}_{safe_name}"
        temp_file_path = os.path.join(TEMP_DIR, temp_filename)

        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"[INVOICE SAVE] {temp_file_path}")

        status, reason, logs = validate_file(temp_file_path)
        logger.info(f"[VALIDATION] {status} | {reason}")

        final_path = move_file(temp_file_path, status)

        if CLEARVIEW_AVAILABLE:
            file_id = save_file_record(
                #file.filename, final_path, "pdf",
                file.filename,
                final_path,
                file.filename.split(".")[-1].lower(),
                os.path.getsize(final_path), status, reason, "invoice",
            )
            save_validation_logs(file_id, logs)
        else:
            file_id = save_file(
                file.filename, final_path, "pdf",
                os.path.getsize(final_path), status, reason, "DATA", "INVOICE",
            )
        logger.info(f"[DB SAVED] invoice file_id={file_id}")

        if status != "VALID":
            return JSONResponse(status_code=400, content={"ok": False, "message": reason})

        _invoice_decisions[file_id] = {"state": "running", "file_id": file_id}
        background_tasks.add_task(run_invoice_decision_pipeline, final_path, file_id)
        logger.info(f"[BACKGROUND TASK STARTED] file_id={file_id}")

        return {"ok": True, "file_id": file_id, "message": "Invoice decision pipeline running"}

    except Exception as ex:
        logger.exception("[UPLOAD INVOICE ERROR]")
        raise HTTPException(status_code=500, detail=str(ex))


# =============================================================================
# ROUTE — INVOICE DECISION STATUS
# GET /invoice-decision/{file_id}
# =============================================================================

@app.get("/invoice-decision/{file_id}")
async def invoice_decision(file_id: int):
    entry = _invoice_decisions.get(file_id)
    if entry is None:
        return JSONResponse(status_code=404, content={"ok": False, "message": "No decision found"})
    return JSONResponse(status_code=200, content={"ok": True, **entry})


# =============================================================================
# ROUTES — DATA APIs  (read from main tables)
# =============================================================================

@app.get("/po")
def po():
    return get_data("po_data", "files")

@app.get("/pr")
def pr():
    return get_data("pr_data", "files")

@app.get("/invoice")
def invoice():
    return get_data("invoice_data", "files")

@app.get("/sow")
def sow():
    return get_data("sow_data", "files")

@app.get("/msa")
def msa():
    return get_data("msa_data", "files")


# =============================================================================
# ROUTES — DATASET APIs  (read from dataset tables with active_flag)
# =============================================================================

@app.get("/po-dataset")
def po_dataset():
    return get_dataset_data("po_dataset", "PO")

@app.get("/pr-dataset")
def pr_dataset():
    return get_dataset_data("pr_dataset", "PR")

@app.get("/invoice-dataset")
def invoice_dataset():
    return get_dataset_data("invoice_dataset", "INVOICE")

@app.get("/sow-dataset")
def sow_dataset():
    return get_dataset_data("sow_dataset", "SOW")

@app.get("/msa-dataset")
def msa_dataset():
    return get_dataset_data("msa_dataset", "MSA")


# =============================================================================
# ROUTE — FILE LIST
# GET /files
# =============================================================================

@app.get("/files")
def list_files():
    if not os.path.exists(INPUT_DIR):
        return []
    files = []
    for name in os.listdir(INPUT_DIR):
        full_path = os.path.join(INPUT_DIR, name)
        if os.path.isfile(full_path):
            stat = os.stat(full_path)
            files.append({
                "name":     name,
                "size":     stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return files


# =============================================================================
# STARTUP
# =============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info(SEP)
    logger.info("ClearView Document Pipeline + AI Document Agent — FastAPI")
    logger.info("URL           : http://127.0.0.1:8000")
    logger.info(f"Backend dir   : {BACKEND_DIR}")
    logger.info(f"Input dir     : {INPUT_DIR}")
    logger.info(f"Temp dir      : {TEMP_DIR}")
    logger.info(f"Logs dir      : {LOG_DIR}")
    logger.info(f"ClearView     : {'✅ Available' if CLEARVIEW_AVAILABLE else '⚠️  Not available (processor/main/pipeline_status missing)'}")
    logger.info("CORS          : localhost:3000 + localhost:5173 + wildcard allowed")
    logger.info("Routes        :")
    logger.info("  POST /upload-file      → sync pipeline (DQ→OCR→classify→extract→insert)")
    logger.info("  POST /upload           → async ClearView background pipeline")
    logger.info("  POST /upload-invoice   → async invoice decision pipeline")
    logger.info("  GET  /status/{id}      → pipeline status")
    logger.info("  GET  /invoice-decision/{id} → invoice decision result")
    logger.info("  GET  /po /pr /invoice /sow /msa → data tables")
    logger.info("  GET  /po-dataset /pr-dataset ... → dataset tables")
    logger.info("  GET  /files /health /health/ollama")
    logger.info("Ready.")
    logger.info(SEP)