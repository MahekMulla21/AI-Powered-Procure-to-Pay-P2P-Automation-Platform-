# ─────────────────────────────────────────────────────────────
# decision_agent/agent_main.py
#
# Main orchestrator for invoice document cross-referencing.
#
# Flow:
#   1. Extract reference IDs from invoice (PO, PR, MSA, SOW, GRN)
#   2. Query PO / PR / MSA / SOW tables concurrently
#   3. Build signals dict (reference match results)
#   4. Run rules_engine  →  cross-reference checks, no LLM
#      - fail → REJECT immediately with specific reason
#      - pass → call decision_engine (LLM) with structured signals + RAG context
#   5. Save verdict → invoice_decision_log table
#   6. Write log file → decision_agent/logs/
#   7. Print to terminal
#   8. Return verdict dict
#
# NOTE: Duplicate detection is NOT performed.
#       The agent only cross-checks references against other documents.
# ─────────────────────────────────────────────────────────────

import re
import json
import os
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .postgres_checker import (
    check_po, check_pr, check_msa, check_sow, save_verdict,
    find_pr_by_reference,
)
from .rules_engine     import run as run_rules
from .decision_engine  import call_llm
from .terminal_printer import print_invoice, print_signals, print_verdict
from .config           import LOG_DIR

# --- 3rd Data Source: Context Builder ---
try:
    # Try absolute import first (standard)
    from decision_agent.context_builder.context_intelligence import run_context_pipeline
except ImportError:
    try:
        # Try relative import
        from ..context_builder.context_intelligence import run_context_pipeline
    except ImportError:
        # Final fallback: Manual path injection
        import sys
        from pathlib import Path
        _ctx_path = Path(__file__).resolve().parent.parent / "context_builder"
        if str(_ctx_path) not in sys.path:
            sys.path.append(str(_ctx_path))
        from context_intelligence import run_context_pipeline # type: ignore


# ─────────────────────────────────────────────────────────────
# EXTRACT REFERENCE IDs
# ─────────────────────────────────────────────────────────────
def _refs(invoice: dict) -> dict:
    return {
        "invoice_number": (invoice.get("invoice_number") or invoice.get("invoice_id") or "").strip(),
        "po_id":  (
            invoice.get("po_reference_number") or invoice.get("po_number")
            or invoice.get("po_id") or ""
        ).strip(),
        "pr_id":  (invoice.get("pr_number") or invoice.get("pr_id") or "").strip(),
        "msa_id": (
            invoice.get("msa_id") or invoice.get("msa_reference")
            or invoice.get("reference_msa") or ""
        ).strip(),
        "sow_id": (
            invoice.get("sow_id") or invoice.get("sow_reference")
            or invoice.get("reference_sow") or ""
        ).strip(),
        "vendor":  (invoice.get("vendor_name") or "").strip().lower(),
        "client":  (invoice.get("client_name") or invoice.get("bill_to") or invoice.get("customer_name") or "").strip().lower(),
        "grn":     (invoice.get("grn_reference") or invoice.get("grn_number") or "").strip(),
        "amount":  _to_float(invoice.get("total_amount")),
        "date":    invoice.get("invoice_date"),
    }


# ─────────────────────────────────────────────────────────────
# BUILD SIGNALS FROM DB RESULTS
# ─────────────────────────────────────────────────────────────
def _signals(refs: dict, db: dict) -> dict:
    today   = date.today()
    po_row  = db.get("po_row")
    msa_row = db.get("msa_row")
    sow_row = db.get("sow_row")

    sig = {
        # ── Invoice / duplicate ───────────────────────────────
        # ── PO ───────────────────────────────────────────────
        "po_found":          po_row is not None,
        "po_status":         po_row.get("po_status") if po_row else None,
        "po_date_valid":     False,
        "amount_within_po":  False,
        "vendor_match":      None,
        # ── PR ───────────────────────────────────────────────
        "pr_found":          db.get("pr_row") is not None,
        "pr_status":         (db.get("pr_row") or {}).get("status"),
        # ── MSA ──────────────────────────────────────────────
        "msa_found":         msa_row is not None,
        "msa_status":        msa_row.get("status") if msa_row else None,
        "msa_valid":         False,
        # ── SOW ──────────────────────────────────────────────
        "sow_found":         sow_row is not None,
        "sow_status":        sow_row.get("status") if sow_row else None,
        "sow_date_valid":    False,
        "amount_within_sow": False,
        # ── Extra fields ──────────────────────────────────────
        "client_name":       refs.get("client") or "not provided",
        "grn_reference":     refs.get("grn") or "not provided",
        "msa_reference":     refs.get("msa_id") or "not provided",
        "sow_reference":     refs.get("sow_id") or "not provided",
        "po_reference":      refs.get("po_id") or "not provided",
        "vendor_name":       refs.get("vendor") or "not provided",
    }

    if po_row:
        s, e = po_row.get("start_date"), po_row.get("end_date")
        d = _parse_date(refs["date"])
        if s and e and d:
            sig["po_date_valid"] = s <= d <= e
        po_amt = po_row.get("total_amount")
        if po_amt is not None and refs["amount"] is not None:
            sig["amount_within_po"] = refs["amount"] <= po_amt
        pv = (po_row.get("vendor_name") or "").strip().lower()
        if pv:
            sig["vendor_match"] = pv == refs["vendor"]
        # Check MSA / SOW references from PO
        sig["po_links_msa"] = po_row.get("reference_msa", "")
        sig["po_links_sow"] = po_row.get("reference_sow", "")

    if msa_row:
        ms = (msa_row.get("status") or "").lower()
        me = msa_row.get("end_date")
        sig["msa_valid"] = ms == "active" and (me is None or me >= today)

    if sow_row:
        sd = _parse_date(refs["date"])
        ss, se = sow_row.get("start_date"), sow_row.get("end_date")
        if sd and ss and se:
            sig["sow_date_valid"] = ss <= sd <= se

        sv = sow_row.get("total_value")
        if sv is not None and refs["amount"] is not None:
            sig["amount_within_sow"] = refs["amount"] <= sv

    return sig


# ─────────────────────────────────────────────────────────────
# WRITE LOG FILE
# ─────────────────────────────────────────────────────────────
def _write_log(invoice_number: str, file_id, verdict: dict) -> None:
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe     = re.sub(r"[^\w\-]", "_", invoice_number or "unknown")
    filepath = os.path.join(LOG_DIR, f"{ts}_{safe}_decision.log")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("Invoice Decision Log\n")
        f.write("=" * 50 + "\n")
        f.write(f"Invoice   : {invoice_number}\n")
        f.write(f"File ID   : {file_id}\n")
        f.write(f"Timestamp : {ts}\n")
        f.write(f"Verdict   : {verdict.get('verdict', '').upper()}\n")
        f.write(f"Confidence: {verdict.get('confidence', 0):.0%}\n")
        f.write(f"Summary   : {verdict.get('summary', '')}\n")
        f.write("=" * 50 + "\n")
        reasons = verdict.get("reasons", [])
        if reasons:
            f.write(f"Rejection Reasons ({len(reasons)}):\n")
            for i, r in enumerate(reasons, 1):
                f.write(f"  {i}. [{r.get('code')}] {r.get('field')} = {r.get('value')}\n")
                f.write(f"     {r.get('message')}\n")
        else:
            f.write("No rejection reasons.\n")
        f.write("=" * 50 + "\n")
        f.write("Signals:\n")
        for k, v in verdict.get("signals", {}).items():
            f.write(f"  {k:<25}: {v}\n")

    print(f"[DECISION AGENT] Log saved → {filepath}")


# ─────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────
def run(invoice: dict, file_id=None, rag_context: str = None) -> dict:
    """
    Args:
        invoice (dict)     : invoice row from invoice_dataset or structured extraction
        file_id (int)      : optional, for audit log
        rag_context (str)  : optional pre-fetched RAG context from FAISS

    Returns:
        dict : verdict with verdict, confidence, reasons, signals, summary, rag_context
    """
    refs           = _refs(invoice)
    invoice_number = refs["invoice_number"] or "UNKNOWN"

    print(f"\n[DECISION AGENT] {'='*50}")
    print(f"[DECISION AGENT] Processing → {invoice_number}")
    print(f"[DECISION AGENT] {'='*50}\n")

    # ── Step 1: Concurrent DB lookups ─────────────────────────
    tasks = {}
    if refs["po_id"]:
        tasks["po_row"]  = (check_po,  refs["po_id"])
    if refs["pr_id"]:
        tasks["pr_row"]  = (check_pr,  refs["pr_id"])
    if refs["msa_id"]:
        tasks["msa_row"] = (check_msa, refs["msa_id"])
    if refs["sow_id"]:
        tasks["sow_row"] = (check_sow, refs["sow_id"])

    db = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        fmap = {pool.submit(fn, arg): name for name, (fn, arg) in tasks.items()}
        for future in as_completed(fmap):
            name = fmap[future]
            try:
                db[name] = future.result()
            except Exception as e:
                print(f"[DECISION AGENT][ERROR] task '{name}': {e}")
                db[name] = None

    # If PO links to MSA/SOW/PR not directly on invoice, fetch them
    po_row = db.get("po_row") or {}
    if not refs["msa_id"] and po_row.get("reference_msa"):
        db["msa_row"] = check_msa(po_row["reference_msa"])
    if not refs["sow_id"] and po_row.get("reference_sow"):
        db["sow_row"] = check_sow(po_row["reference_sow"])
    
    # Smart PR lookup: Invoice -> PO link -> SOW link
    if not db.get("pr_row"):
        if refs["pr_id"]:
            db["pr_row"] = check_pr(refs["pr_id"])
        elif po_row.get("reference_pr"):
            db["pr_row"] = check_pr(po_row["reference_pr"])
        elif refs["sow_id"] or po_row.get("reference_sow"):
            target_sow = refs["sow_id"] or po_row.get("reference_sow")
            db["pr_row"] = find_pr_by_reference(sow_id=target_sow)
        elif refs["msa_id"] or po_row.get("reference_msa"):
            target_msa = refs["msa_id"] or po_row.get("reference_msa")
            db["pr_row"] = find_pr_by_reference(msa_id=target_msa)

    # ── Step 2: Build signals ─────────────────────────────────
    sig = _signals(refs, db)
    print_signals(sig)

    # ── Step 3: Hard rules ────────────────────────────────────
    failures = run_rules(invoice, db)

    if failures:
        verdict = {
            "verdict":    "rejected",
            "confidence": 1.0,
            "reasons":    failures,
            "signals":    sig,
            "summary":    f"{failures[0]['code']}: {failures[0]['message']}",
        }
    else:
        # ── Step 4: Fetch 3rd Data Source (Business Context) ──
        print("[DECISION AGENT] Fetching Business Context from Context Builder...")
        try:
            business_context = run_context_pipeline()
        except Exception as e:
            print(f"[DECISION AGENT][WARN] Context Builder failed: {e}")
            business_context = "No additional business context found."

        # ── Step 5: LLM (with RAG + Business Context) ─────────
        llm = call_llm(
            invoice, db, sig, 
            rag_context=rag_context, 
            business_context=business_context,
            file_id=file_id
        )
        
        # Robust confidence parsing
        raw_conf = llm.get("confidence", 0.5)
        try:
            if isinstance(raw_conf, str):
                conf_val = float(raw_conf.replace("%", "")) / (100.0 if "%" in raw_conf else 1.0)
            else:
                conf_val = float(raw_conf)
        except (ValueError, TypeError):
            conf_val = 0.5

        verdict = {
            "verdict":     llm.get("verdict", "needs_review"),
            "confidence":  conf_val,
            "reasons":     llm.get("reasons", []),
            "signals":     sig,
            "summary":     llm.get("summary", ""),
            "rag_context": rag_context or "",
        }
        print(f"[DECISION AGENT] LLM Verdict Received | file_id={file_id}")

    # ── Step 5: Save to DB ────────────────────────────────────
    save_verdict(invoice_number, file_id, verdict)

    # ── Step 6: Write log ─────────────────────────────────────
    _write_log(invoice_number, file_id, verdict)

    # ── Step 7: Print terminal ────────────────────────────────
    print_verdict(invoice_number, verdict)

    return verdict


# ── helpers ──────────────────────────────────────────────────
def _to_float(value):
    if value is None:
        return None
    try:
        import re
        cleaned = re.sub(r"[^\d.]", "", str(value).replace(",", ""))
        return float(cleaned) if cleaned else None
    except Exception:
        return None


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except Exception:
            continue
    return None
