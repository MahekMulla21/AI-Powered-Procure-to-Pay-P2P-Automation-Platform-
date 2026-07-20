# ─────────────────────────────────────────────────────────────
# decision_agent/rules_engine.py
#
# Hard deterministic cross-reference checks.
# Validates invoice references against PO / PR / MSA / SOW tables.
# Returns list of reason dicts for every rule that fails.
# Empty list = all rules passed -> proceed to LLM.
#
# NOTE: Duplicate detection is intentionally NOT performed here.
#       The agent's sole job is validating document cross-references.
# ─────────────────────────────────────────────────────────────

import re
from datetime import date, datetime


def run(invoice: dict, db: dict) -> list[dict]:
    """
    Args:
        invoice : dict from invoice_dataset (or structured pipeline)
        db      : {invoice_row, po_row, pr_row, msa_row, sow_row}

    Returns:
        list of reason dicts — empty means all rules passed
    """
    reasons = []
    today   = date.today()


    inv_row = db.get("invoice_row")
    po_row  = db.get("po_row")
    pr_row  = db.get("pr_row")
    msa_row = db.get("msa_row")
    sow_row = db.get("sow_row")

    invoice_number = invoice.get("invoice_number") or invoice.get("invoice_id", "")
    invoice_amount = _to_float(invoice.get("total_amount"))
    invoice_date   = _parse_date(invoice.get("invoice_date"))
    vendor_name    = (invoice.get("vendor_name") or "").strip().lower()
    po_ref         = invoice.get("po_reference_number") or invoice.get("po_number") or invoice.get("po_id")
    pr_ref         = invoice.get("pr_number") or invoice.get("pr_id")
    msa_ref        = invoice.get("msa_id")
    sow_ref        = invoice.get("sow_id")

    # ── Rule 1 : Mandatory References ──────────────────────
    # Ensure all required references are present
    if not po_ref:
        reasons.append({
            "code":    "MISSING_PO_REFERENCE",
            "field":   "po_reference_number",
            "value":   None,
            "message": "Mandatory PO reference is missing from the invoice.",
        })
    if not pr_ref and not db.get("pr_row"):
        reasons.append({
            "code":    "MISSING_PR_REFERENCE",
            "field":   "pr_number",
            "value":   None,
            "message": "Mandatory PR reference is missing from both the invoice and the linked PO.",
        })
    if not msa_ref and not db.get("msa_row"):
        reasons.append({
            "code":    "MISSING_MSA_REFERENCE",
            "field":   "msa_id",
            "value":   None,
            "message": "Mandatory MSA reference is missing from both the invoice and the linked PO.",
        })
    if not sow_ref and not db.get("sow_row"):
        reasons.append({
            "code":    "MISSING_SOW_REFERENCE",
            "field":   "sow_id",
            "value":   None,
            "message": "Mandatory SOW reference is missing from both the invoice and the linked PO.",
        })

    # ── Rule 2 : PO checks ────────────────────────────────────
    if po_ref:
        if po_row is None:
            reasons.append({
                "code":    "PO_NOT_FOUND",
                "field":   "po_reference_number",
                "value":   po_ref,
                "message": f"Purchase Order '{po_ref}' not found in po_dataset.",
            })
        else:
            po_status = (po_row.get("po_status") or "").lower()

            if po_status in ("closed", "cancelled", "expired", "inactive"):
                reasons.append({
                    "code":    "PO_INACTIVE",
                    "field":   "po_reference_number",
                    "value":   po_ref,
                    "message": f"PO '{po_ref}' status is '{po_row.get('po_status')}' — cannot bill against it.",
                })

            po_start = po_row.get("start_date")
            po_end   = po_row.get("end_date")
            if po_start and po_end and invoice_date:
                if not (po_start <= invoice_date <= po_end):
                    reasons.append({
                        "code":    "PO_DATE_INVALID",
                        "field":   "invoice_date",
                        "value":   str(invoice_date),
                        "message": f"Invoice date {invoice_date} is outside PO valid period ({po_start} -> {po_end}).",
                    })

            po_amount = po_row.get("total_amount")
            if po_amount is not None and invoice_amount is not None:
                if invoice_amount > po_amount:
                    reasons.append({
                        "code":    "AMOUNT_EXCEEDS_PO",
                        "field":   "total_amount",
                        "value":   str(invoice_amount),
                        "message": f"Invoice amount {invoice_amount} exceeds PO approved amount {po_amount}.",
                    })

            po_vendor = (po_row.get("vendor_name") or "").strip().lower()
            if po_vendor and vendor_name and po_vendor != vendor_name:
                reasons.append({
                    "code":    "VENDOR_MISMATCH",
                    "field":   "vendor_name",
                    "value":   invoice.get("vendor_name"),
                    "message": f"Vendor on invoice '{invoice.get('vendor_name')}' does not match PO vendor '{po_row.get('vendor_name')}'.",
                })

    # ── Rule 3 : PR checks ────────────────────────────────────
    if pr_ref:
        if pr_row is None:
            reasons.append({
                "code":    "PR_NOT_FOUND",
                "field":   "pr_number",
                "value":   pr_ref,
                "message": f"Purchase Request '{pr_ref}' not found in pr_dataset.",
            })
        else:
            pr_status = (pr_row.get("status") or "").lower()
            if pr_status not in ("approved", "active", "open"):
                reasons.append({
                    "code":    "PR_NOT_APPROVED",
                    "field":   "pr_number",
                    "value":   pr_ref,
                    "message": f"PR '{pr_ref}' status is '{pr_row.get('status')}' — only approved PRs are valid.",
                })

    # ── Rule 4 : MSA checks ───────────────────────────────────
    effective_msa = msa_ref or (po_row.get("reference_msa") if po_row else None)
    if effective_msa:
        if msa_row is None:
            reasons.append({
                "code":    "MSA_NOT_FOUND",
                "field":   "msa_id",
                "value":   effective_msa,
                "message": f"MSA '{effective_msa}' not found in msa_dataset.",
            })
        else:
            msa_status = (msa_row.get("status") or "").lower()
            msa_expiry = msa_row.get("end_date")
            if msa_status != "active" or (msa_expiry and msa_expiry < today):
                reasons.append({
                    "code":    "MSA_EXPIRED",
                    "field":   "msa_id",
                    "value":   effective_msa,
                    "message": f"MSA '{effective_msa}' status='{msa_row.get('status')}' expired={msa_expiry}.",
                })

    # ── Rule 5 : SOW checks ───────────────────────────────────
    effective_sow = sow_ref or (po_row.get("reference_sow") if po_row else None)
    if effective_sow:
        if sow_row is None:
            reasons.append({
                "code":    "SOW_NOT_FOUND",
                "field":   "sow_id",
                "value":   effective_sow,
                "message": f"SOW '{effective_sow}' not found in sow_dataset.",
            })
        else:
            sow_status = (sow_row.get("status") or "").lower()
            sow_start  = sow_row.get("start_date")
            sow_end    = sow_row.get("end_date")

            # Logging as requested
            print(f"[RULES_ENGINE] SOW Validation for {effective_sow}:")
            print(f"  invoice_date : {invoice_date}")
            print(f"  sow_start    : {sow_start}")
            print(f"  sow_end      : {sow_end}")

            if sow_status != "active":
                reasons.append({
                    "code":    "SOW_INACTIVE",
                    "field":   "sow_id",
                    "value":   effective_sow,
                    "message": f"SOW '{effective_sow}' status is '{sow_row.get('status')}' — must be active.",
                })
            
            if invoice_date and sow_start and sow_end:
                if not (sow_start <= invoice_date <= sow_end):
                    reasons.append({
                        "code":    "SOW_DATE_INVALID",
                        "field":   "invoice_date",
                        "value":   str(invoice_date),
                        "message": f"Invoice date {invoice_date} is outside SOW valid period ({sow_start} -> {sow_end}).",
                    })
                print(f"  validation_result: {'REJECT' if not (sow_start <= invoice_date <= sow_end) else 'PASS'}")
            elif not invoice_date:
                print("  validation_result: SKIP (No invoice_date found)")
            else:
                print("  validation_result: PASS (Missing SOW dates)")

            sow_value = sow_row.get("total_value")
            if sow_value is not None and invoice_amount is not None:
                if invoice_amount > sow_value:
                    reasons.append({
                        "code":    "AMOUNT_EXCEEDS_SOW",
                        "field":   "total_amount",
                        "value":   str(invoice_amount),
                        "message": f"Invoice amount {invoice_amount} exceeds SOW total value {sow_value}.",
                    })

    if reasons:
        print(f"[RULES_ENGINE] {len(reasons)} cross-reference violation(s) -> instant reject")
    else:
        print("[RULES_ENGINE] All reference checks passed -> calling LLM")

    return reasons


# ── helpers ──────────────────────────────────────────────────
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


def _to_float(value):
    if value is None:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(value).replace(",", ""))
        return float(cleaned) if cleaned else None
    except Exception:
        return None
