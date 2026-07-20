# ===============================
# doc_classifier.py (FINAL FIXED 🚀)
# ===============================

def classify_document(text: str) -> str:
    """
    Hybrid classifier:
    1. Strong keyword priority (PR / PO / INVOICE)
    2. Scoring fallback (MSA / SOW)
    """

    if not text:
        return "UNKNOWN"

    t = text.lower()

    # =====================================
    # 🔥 STEP 1: STRONG UNIQUE KEYWORDS
    # =====================================

    # -------- PR --------
    pr_keywords = [
        "purchase requisition",
        "purchase request",
        "requisition number",
        "pr number",
        "request date",
        "requested by",
        "approval status"
    ]

    pr_score = sum(
        1 for k in pr_keywords if k in t
    )

    # -------- PO --------
    po_keywords = [
        "purchase order",
        "purchase order number",
        "po number",
        "po no",
        "order number",
        "supplier",
        "vendor",
        "delivery terms",
        "billing address",
        "ship to",
        "buyer",
        "delivery location"
    ]

    po_score = sum(
        1 for k in po_keywords if k in t
    )

    # -------- INVOICE --------
    invoice_keywords = [
        "invoice number",
        "tax invoice",
        "invoice date",
        "bill to",
        "total amount due",
        "invoice total",
        "invoice no"
    ]

    invoice_score = sum(
        1 for k in invoice_keywords if k in t
    )

    # =====================================
    # 🔥 STEP 2: DECISION
    # =====================================

    # -------- PR --------
    if (
        pr_score >= 2
        and pr_score > po_score
        and pr_score > invoice_score
    ):
        return "PR"

    # -------- PO --------
    if (
        po_score >= 2
        and po_score >= invoice_score
    ):
        return "PO"

    # -------- INVOICE --------
    if invoice_score >= 2:
        return "INVOICE"

    # =====================================
    # 🔥 STEP 3: EXTRA FALLBACK CHECKS
    # =====================================

    # -------- PO --------
    if (
        "purchase order" in t
        or "po number" in t
        or "po no" in t
    ):
        return "PO"

    # -------- INVOICE --------
    if (
        "invoice number" in t
        or "tax invoice" in t
        or "invoice date" in t
        or "invoice no" in t
    ):
        return "INVOICE"

    # -------- PR --------
    if (
        "purchase requisition" in t
        or "purchase request" in t
        or "pr number" in t
    ):
        return "PR"

    # =====================================
    # 🔥 STEP 4: LOW PRIORITY DOCS
    # =====================================

    scores = {
        "MSA": 0,
        "SOW": 0
    }

    # -------- MSA --------
    msa_keywords = [
        "master service agreement",
        "msa",
        "termination clause",
        "governing law",
        "indemnification",
        "confidentiality"
    ]

    for k in msa_keywords:
        if k in t:
            scores["MSA"] += 2

    # -------- SOW --------
    sow_keywords = [
        "statement of work",
        "scope of work",
        "deliverables",
        "milestones",
        "project scope"
    ]

    for k in sow_keywords:
        if k in t:
            scores["SOW"] += 2

    # =====================================
    # 🔥 STEP 5: FINAL FALLBACK
    # =====================================

    best_doc = max(
        scores,
        key=scores.get
    )

    if scores[best_doc] > 0:
        return best_doc

    return "UNKNOWN"