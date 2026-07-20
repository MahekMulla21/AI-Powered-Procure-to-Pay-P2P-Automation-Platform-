# Invoice_field_definitions.py
# ─────────────────────────────────────────────────────────────────
# Declares every field to be extracted, along with:
#   anchor_keys – ordered list of label strings for dictionary search
#   query       – semantic search query sent to the FAISS index
#   llm_hint    – task instruction passed to the LLM
#
# Structured fields  → anchor + FAISS fallback + LLM refinement
# Unstructured fields → FAISS retrieval + LLM narrative generation
# ─────────────────────────────────────────────────────────────────

STRUCTURED_FIELD_DEFINITIONS: dict[str, dict] = {
    "invoice_number": {
        "anchor_keys": ["Invoice #:", "Invoice #", "INV-"],
        "query"      : "invoice number reference ID",
        "llm_hint"   : "Extract the invoice number (e.g. INV-CM-2024-XXXX).",
    },
    "vendor_name": {
        "anchor_keys": ["FROM (VENDOR)", "CloudMinds"],
        "query"      : "vendor supplier company name from",
        "llm_hint"   : "Extract the full vendor / supplier company name.",
    },
    "invoice_date": {
        "anchor_keys": ["Invoice Date:", "Date:"],
        "query"      : "invoice date issued on",
        "llm_hint"   : "Extract the invoice date (format: Month DD, YYYY).",
    },
    "due_date": {
        "anchor_keys": ["Due Date:", "Net 30"],
        "query"      : "due date payment deadline",
        "llm_hint"   : "Extract the payment due date.",
    },
    "po_reference": {
        "anchor_keys": ["Reference PO:", "PO-"],
        "query"      : "purchase order PO number reference",
        "llm_hint"   : "Extract the PO reference number (e.g. PO-XXXX-XXXXX).",
    },
    "grn_reference": {
        "anchor_keys": ["GRN Reference:", "GRN-"],
        "query"      : "GRN goods receipt note reference",
        "llm_hint"   : "Extract the GRN reference number.",
    },
    "hsn_code": {
        "anchor_keys": ["HSN/SAC", "998313"],
        "query"      : "HSN SAC service code",
        "llm_hint"   : "Extract the HSN or SAC code for the service.",
    },
    "quantity": {
        "anchor_keys": ["Qty", "1 LS"],
        "query"      : "quantity units lump sum",
        "llm_hint"   : "Extract the quantity and unit (e.g. '1 LS').",
    },
    "unit_price": {
        "anchor_keys": ["Unit Rate (USD)", "Rate (USD)"],
        "query"      : "unit rate price per unit USD",
        "llm_hint"   : "Extract the unit rate / price in USD.",
    },
    "total_amount": {
        "anchor_keys": ["TOTAL DUE", "Amount (USD)", "SUBTOTAL"],
        "query"      : "total amount due invoice value",
        "llm_hint"   : "Extract the final total amount due in USD.",
    },
    "tax": {
        "anchor_keys": ["IGST @", "GST", "Tax"],
        "query"      : "tax GST IGST percentage amount",
        "llm_hint"   : "Extract the tax type, rate, and amount (e.g. IGST @ 0% = 0.00 USD).",
    },
    "currency": {
        "anchor_keys": ["Currency:", "USD", "US Dollar"],
        "query"      : "currency denomination USD dollar",
        "llm_hint"   : "Extract the currency code and name.",
    },
    "company_code": {
        "anchor_keys": ["Company Code:", "CloudMinds – IN"],
        "query"      : "company code internal identifier",
        "llm_hint"   : "Extract the company code field value.",
    },
    "status": {
        "anchor_keys": ["Status:", "PO Status", "3-Way Match", "Milestone Accepted"],
        "query"      : "status PO match milestone accepted",
        "llm_hint"   : "Extract the invoice / PO status description.",
    },
    "tax_breakup": {
        "anchor_keys": ["TAX BREAKUP", "Tax Component", "IGST", "CGST", "SGST", "Withholding"],
        "query"      : "tax breakup component IGST CGST SGST withholding rate amount",
        "llm_hint"   : "Extract the complete tax breakup table as a structured dict with keys: component, rate, taxable_amount, tax_amount.",
    },
    "bank_details": {
        "anchor_keys": ["PAYMENT INSTRUCTIONS", "Bank Name", "HDFC Bank", "IFSC", "SWIFT", "Account No"],
        "query"      : "bank payment wire transfer IFSC SWIFT account number",
        "llm_hint"   : "Extract all bank / payment details as a structured dict with keys: bank_name, account_name, account_no, ifsc, swift.",
    },
}

UNSTRUCTURED_FIELD_DEFINITIONS: dict[str, dict] = {
    "description_of_service": {
        "query"   : "description of service deliverable milestone cloud assessment",
        "top_k"   : 4,
        "llm_hint": (
            "Extract a clean, full description of the service(s) provided in this invoice, "
            "including deliverable name, milestone, delivery date, and acceptance reference "
            "if present. Write 2-4 sentences in plain English. Do NOT use bullet points."
        ),
    },
}
