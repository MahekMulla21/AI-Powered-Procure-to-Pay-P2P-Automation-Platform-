"""
main.py — Single entry point for MSA / SOW / Invoice pipeline runners.
Place this file in: backend/
"""
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import argparse
import concurrent.futures
import logging
import os
import time
import traceback
import threading

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


# ── Thread-aware Pipeline Log Filter ──────────────────────────────────────────
class PipelineFilter(logging.Filter):
    _labels: dict = {}
    _lock = threading.Lock()

    @classmethod
    def set(cls, label: str) -> None:
        with cls._lock:
            cls._labels[threading.current_thread().ident] = label

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._labels.pop(threading.current_thread().ident, None)

    def filter(self, record: logging.LogRecord) -> bool:
        label = self._labels.get(threading.current_thread().ident, "")
        if label:
            record.msg = f"[{label}] {record.msg}"
        return True


_pipeline_filter = PipelineFilter()
logging.getLogger().addFilter(_pipeline_filter)

for _noisy in ["httpx", "sentence_transformers", "faiss", "faiss.loader",
               "numexpr", "numexpr.utils", "paddle", "ppocr"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def _pipeline_banner(label: str, file_path: str, file_id, event: str) -> None:
    tag   = f"[{label}]"
    fname = os.path.basename(file_path)
    sep   = "=" * 70
    logger.info(sep)
    logger.info("%s  %s  |  File ID: %s  |  %s", tag, event, file_id, fname)
    logger.info(sep)


# ── PR  ────────────────────────────────────────────────────────────────────────
def run_pr_pipeline(file_path: str, file_id: int | None = None) -> dict:
    PipelineFilter.set("PR")
    pipeline_logger = logging.getLogger("PR")
    start = time.time()
    try:
        _pipeline_banner("PR", file_path, file_id, "STARTED")
        from pr_main import process_file
        proc_result = process_file(file_path, file_id)
        elapsed = time.time() - start
        _pipeline_banner("PR", file_path, file_id, f"COMPLETED in {elapsed:.2f}s")
        return {
            "pipeline":     "PR",
            "status":       "success",
            "file_id":      file_id,
            "elapsed_sec":  round(elapsed, 2),
            "match_status": proc_result.get("match_status", "UNKNOWN"),
            "doc_id":       proc_result.get("doc_id", ""),
        }
    except Exception as exc:
        elapsed = time.time() - start
        pipeline_logger.error("[PR] FAILED after %.2fs: %s", elapsed, exc)
        pipeline_logger.debug(traceback.format_exc())
        return {"pipeline": "PR", "status": "failed", "file_id": file_id,
                "error": str(exc), "elapsed_sec": round(elapsed, 2)}
    finally:
        PipelineFilter.clear()

# ── PO ────────────────────────────────────────────────────────────────────────
def run_po_pipeline(file_path: str, file_id: int | None = None) -> dict:
    PipelineFilter.set("PO")
    pipeline_logger = logging.getLogger("PO")
    start = time.time()
    try:
        _pipeline_banner("PO", file_path, file_id, "STARTED")
        from po_main import process_file
        proc_result = process_file(file_path, file_id)
        elapsed = time.time() - start
        _pipeline_banner("PO", file_path, file_id, f"COMPLETED in {elapsed:.2f}s")
        return {
            "pipeline":     "PO",
            "status":       "success",
            "file_id":      file_id,
            "elapsed_sec":  round(elapsed, 2),
            "match_status": proc_result.get("match_status", "UNKNOWN"),
            "doc_id":       proc_result.get("doc_id", ""),
        }
    except Exception as exc:
        elapsed = time.time() - start
        pipeline_logger.error("[PO] FAILED after %.2fs: %s", elapsed, exc)
        pipeline_logger.debug(traceback.format_exc())
        return {"pipeline": "PO", "status": "failed", "file_id": file_id,
                "error": str(exc), "elapsed_sec": round(elapsed, 2)}
    finally:
        PipelineFilter.clear()

# ── SOW ────────────────────────────────────────────────────────────────────────
def run_sow_pipeline(file_path: str, file_id: int | None = None) -> dict:
    PipelineFilter.set("SOW")
    pipeline_logger = logging.getLogger("SOW")
    start = time.time()
    try:
        _pipeline_banner("SOW", file_path, file_id, "STARTED")
        from sow_main import process_file
        proc_result = process_file(file_path, file_id)
        elapsed = time.time() - start
        _pipeline_banner("SOW", file_path, file_id, f"COMPLETED in {elapsed:.2f}s")
        return {
            "pipeline":     "SOW",
            "status":       "success",
            "file_id":      file_id,
            "elapsed_sec":  round(elapsed, 2),
            "match_status": proc_result.get("match_status", "UNKNOWN"),
            "doc_id":       proc_result.get("doc_id", ""),
        }
    except Exception as exc:
        elapsed = time.time() - start
        pipeline_logger.error("[SOW] FAILED after %.2fs: %s", elapsed, exc)
        pipeline_logger.debug(traceback.format_exc())
        return {"pipeline": "SOW", "status": "failed", "file_id": file_id,
                "error": str(exc), "elapsed_sec": round(elapsed, 2)}
    finally:
        PipelineFilter.clear()


# ── MSA ────────────────────────────────────────────────────────────────────────
def run_msa_pipeline(file_path: str, file_id: int | None = None) -> dict:
    PipelineFilter.set("MSA")
    pipeline_logger = logging.getLogger("MSA")
    start = time.time()
    try:
        _pipeline_banner("MSA", file_path, file_id, "STARTED")
        from msa_main import process_file
        proc_result = process_file(file_path, file_id)
        elapsed = time.time() - start
        _pipeline_banner("MSA", file_path, file_id, f"COMPLETED in {elapsed:.2f}s")
        return {
            "pipeline":     "MSA",
            "status":       "success",
            "file_id":      file_id,
            "elapsed_sec":  round(elapsed, 2),
            "match_status": proc_result.get("match_status", "UNKNOWN"),
            "doc_id":       proc_result.get("doc_id", ""),
        }
    except Exception as exc:
        elapsed = time.time() - start
        pipeline_logger.error("[MSA] FAILED after %.2fs: %s", elapsed, exc)
        pipeline_logger.debug(traceback.format_exc())
        return {"pipeline": "MSA", "status": "failed", "file_id": file_id,
                "error": str(exc), "elapsed_sec": round(elapsed, 2)}
    finally:
        PipelineFilter.clear()

# ── INVOICE ────────────────────────────────────────────────────────────────────
def run_invoice_pipeline(file_path: str, file_id: int | None = None) -> dict:
    PipelineFilter.set("INVOICE")
    pipeline_logger = logging.getLogger("INVOICE")
    start = time.time()
    try:
        _pipeline_banner("INVOICE", file_path, file_id, "STARTED")
        from invoice_main import process_file
        proc_result = process_file(file_path, file_id)
        elapsed = time.time() - start
        _pipeline_banner("INVOICE", file_path, file_id, f"COMPLETED in {elapsed:.2f}s")
        return {
            "pipeline":     "INVOICE",
            "status":       "success",
            "file_id":      file_id,
            "elapsed_sec":  round(elapsed, 2),
            "match_status": proc_result.get("match_status", "UNKNOWN"),
            "doc_id":       proc_result.get("doc_id", ""),
        }
    except Exception as exc:
        elapsed = time.time() - start
        pipeline_logger.error("[INVOICE] FAILED after %.2fs: %s", elapsed, exc)
        pipeline_logger.debug(traceback.format_exc())
        return {"pipeline": "INVOICE", "status": "failed", "file_id": file_id,
                "error": str(exc), "elapsed_sec": round(elapsed, 2)}
    finally:
        PipelineFilter.clear()

# ── CLI orchestrator (unchanged from original) ─────────────────────────────────
def run_parallel(args: argparse.Namespace) -> None:
    logger.info("=" * 60)
    logger.info("Launching MSA + Invoice pipelines in PARALLEL")
    logger.info("=" * 60)
    overall_start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_msa = executor.submit(run_msa_pipeline, args.msa_pdf, args.msa_file_id)
        future_invoice = executor.submit(run_invoice_pipeline, args.inv_pdf, args.inv_file_id)

        results = []
        for future in concurrent.futures.as_completed([future_msa, future_invoice]):
            try:
                results.append(future.result())
            except Exception as exc:
                logger.error(f"Unexpected executor error: {exc}")
                results.append({"pipeline": "unknown", "status": "failed", "error": str(exc)})

    overall_elapsed = time.time() - overall_start
    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 60)
    all_ok = True
    for r in results:
        icon = "OK" if r["status"] == "success" else "FAIL"
        logger.info(
            "  [%s]  %-10s | status: %-8s | match: %-18s | doc_id: %s | time: %ss",
            icon, r["pipeline"], r["status"],
            r.get("match_status", "?"), r.get("doc_id", "?"),
            r.get("elapsed_sec", "?")
        )
        if r["status"] != "success":
            all_ok = False

    logger.info(f"\n  Total wall-clock time : {overall_elapsed:.2f}s")
    logger.info("=" * 60)

    if not all_ok:
        logger.error("One or more pipelines failed. Check logs above.")
        sys.exit(1)
    logger.info("All pipelines completed successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parallel runner for MSA + Invoice pipelines")
    parser.add_argument("--msa_pdf",     required=True)
    parser.add_argument("--msa_file_id", type=int, default=None)
    parser.add_argument("--inv_pdf",     required=True)
    parser.add_argument("--inv_file_id", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logger.info(f"MSA     → pdf={args.msa_pdf}, file_id={args.msa_file_id}")
    logger.info(f"Invoice → pdf={args.inv_pdf}, file_id={args.inv_file_id}")
    run_parallel(args)