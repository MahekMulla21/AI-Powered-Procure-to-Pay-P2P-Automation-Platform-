# ─────────────────────────────────────────────────────────────
# decision_agent/terminal_printer.py
# ─────────────────────────────────────────────────────────────

SEP  = "=" * 65
LINE = "-" * 65


def print_invoice(invoice: dict) -> None:
    print(SEP)
    print("[DECISION AGENT]  Invoice loaded from invoice_dataset")
    print(LINE)
    print(f"  invoice_number      : {invoice.get('invoice_number', 'N/A')}")
    print(f"  vendor_name         : {invoice.get('vendor_name', 'N/A')}")
    print(f"  invoice_date        : {invoice.get('invoice_date', 'N/A')}")
    print(f"  po_reference_number : {invoice.get('po_reference_number', 'N/A')}")
    print(f"  total_amount        : {invoice.get('total_amount', 'N/A')} {invoice.get('currency', '')}")
    print(f"  grn_reference       : {invoice.get('grn_reference', 'N/A')}")
    print(f"  file_id             : {invoice.get('file_id', 'N/A')}")
    print(SEP)
    print()


def print_signals(signals: dict) -> None:
    print("[DECISION AGENT]  DB Signals")
    print(LINE)
    for k, v in signals.items():
        print(f"  {k:<25} : {v}")
    print()


def print_verdict(invoice_number: str, verdict: dict) -> None:
    v          = verdict.get("verdict", "unknown").upper()
    confidence = verdict.get("confidence", 0)
    summary    = verdict.get("summary", "")
    reasons    = verdict.get("reasons", [])

    icons = {
        "APPROVED":     "✅  APPROVED",
        "REJECTED":     "❌  REJECTED",
        "NEEDS_REVIEW": "⚠️   NEEDS REVIEW",
    }
    label = icons.get(v, f"?  {v}")

    print(SEP)
    print(f"[DECISION AGENT]  Result for invoice: {invoice_number}")
    print(LINE)
    print(f"  Verdict     : {label}")
    print(f"  Confidence  : {confidence:.0%}")
    print(f"  Summary     : {summary}")

    if reasons:
        print(LINE)
        print(f"  Rejection reasons ({len(reasons)}):")
        for i, r in enumerate(reasons, 1):
            print(f"    {i}. [{r.get('code')}]")
            print(f"       Field   : {r.get('field')}")
            print(f"       Value   : {r.get('value')}")
            print(f"       Message : {r.get('message')}")

    print(SEP)
    print()
