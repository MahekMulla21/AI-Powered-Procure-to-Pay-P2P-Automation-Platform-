import re

# ===============================
# STRUCTURED FIELD ALIASES
# ===============================
FIELD_ALIASES = {
    "invoice_number": [
        "invoice number", "invoice no", "invoice#", "inv no",
        "inv number", "invoice id", "bill number", "bill no"
    ],
    "vendor_name": [
        "vendor name", "vendor_name", "vendor-name",
        "service provider", "provider", "vendor",
        "bill from", "billed by", "supplier name", "from"
    ],
    "invoice_date": [
        "invoice date", "bill date", "date of invoice",
        "issued date", "invoice issued", "date"
    ],
    "due_date": [
        "due date", "payment due", "payment due date",
        "due by", "pay by", "payment deadline"
    ],
    "po_reference_number": [
        "po number", "po no", "purchase order", "purchase order number",
        "po reference", "po ref", "p.o. number", "po#",
        "reference po", "ref po"
    ],
    "grn_reference": [
        "grn", "grn number", "grn reference", "goods receipt note",
        "goods receipt number", "grn no", "grn ref", "receipt number"
    ],
    "hsn_code": [
        "hsn code", "hsn", "hsn/sac", "sac code",
        "harmonized code", "tariff code", "hsn number", "sac"
    ],
    "quantity": [
        "quantity", "qty", "units", "no of units",
        "number of units", "count", "nos"
    ],
    "unit_price": [
        "unit price", "rate", "price per unit", "unit rate",
        "unit cost", "cost per unit", "price", "per unit", "unit rate (usd)"
    ],
    "total_amount": [
        "total amount", "total", "grand total", "invoice total",
        "amount due", "net amount", "total due", "amount payable",
        "payable amount", "net payable", "total due"
    ],
    "tax": [
        "tax", "tax amount", "gst", "vat", "tax total",
        "total tax", "igst", "cgst", "sgst", "gst amount"
    ],
    "currency": [
        "currency", "usd", "inr", "eur", "currency code"
    ],
    "company_code": [
        "company code", "company id", "entity code", "cost center",
        "business unit code", "org code", "plant code", "gstin"
    ],
    "status": [
        "status", "invoice status", "payment status", "approval status",
        "milestones billed"
    ],
    "client_name": [
        "client name", "bill to", "billed to", "to (client)", "client",
        "customer name", "customer", "buyer", "sold to", "ship to"
    ]
}

# ===============================
# UNSTRUCTURED FIELD ALIASES
# ===============================
UNSTRUCTURED_ALIASES = {
    "description_of_service": [
        "description of service", "service description", "description",
        "scope of work", "particulars", "nature of service",
        "line items", "item description", "work description", "milestone"
    ],
    "bank_details": [
        "bank details", "bank information", "payment details",
        "bank account", "account details", "wire transfer", "remittance"
    ],
    "tax_breakup": [
        "tax breakup", "tax breakdown", "tax details",
        "cgst", "sgst", "igst", "gst breakup", "tax summary"
    ]
}

# ===============================
# NORMALIZATION
# ===============================
def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ===============================
# DATE EXTRACTION
# ===============================
def extract_date(text):
    # Named month: January 15, 2024
    match = re.search(
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},\s+\d{4}",
        text
    )
    if match:
        return match.group(0)

    # Numeric formats: DD/MM/YYYY  |  MM-DD-YYYY  |  YYYY-MM-DD
    match = re.search(
        r"\b(\d{2}[\/\-]\d{2}[\/\-]\d{4}|\d{4}[\/\-]\d{2}[\/\-]\d{2})\b",
        text
    )
    return match.group(0) if match else None

# ===============================
# AMOUNT EXTRACTION
# ===============================
def extract_amount(text):
    """Pull a numeric amount with optional currency symbol."""
    match = re.search(r"[\$₹€]?\s*[\d,]+(?:\.\d{1,2})?", text)
    return match.group(0).strip() if match else None

# ===============================
# STRICT SECTION EXTRACTION
# ===============================
def extract_section(text, keyword):
    pattern = rf"\d+\.\s*{keyword}.*?\n(.+?)(\n\d+\.|\Z)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None

# ===============================
# VALIDATION
# ===============================
def is_valid_value(field, value):
    if not value:
        return False

    value = value.strip()

    if len(value) < 2:
        return False

    if value.lower() in ["or", "and", "the", "n/a", "-", "nil", "none"]:
        return False

    if field == "currency":
        return value.upper() in ["USD", "INR", "EUR"]

    if field == "vendor_name":
        return len(value.split()) >= 2

    if field == "invoice_number":
        return bool(re.search(r"[a-z0-9\-\/]{3,}", value.lower()))

    if field in ("hsn_code", "company_code", "grn_reference", "po_reference_number"):
        return bool(re.search(r"[a-z0-9]{2,}", value.lower()))

    if field in ("total_amount", "unit_price", "tax", "quantity"):
        return bool(re.search(r"\d", value))

    return True

# ===============================
# UNSTRUCTURED EXTRACTION
# ===============================
def extract_unstructured_sections(text):
    result = {}

    for field, aliases in UNSTRUCTURED_ALIASES.items():
        value = None

        for alias in aliases:
            section = extract_section(text, alias)
            if section:
                value = section[:500]   # cap size
                break

        result[field] = value

    return result

# ===============================
# DEDICATED EXTRACTORS
# (run before generic alias loop)
# ===============================

def _extract_invoice_date(text):
    # Try labeled date first: "Invoice Date: April 27, 2024"
    match = re.search(
        r"(?:invoice\s*date|bill\s*date|date\s*of\s*invoice|issued\s*date)"
        r"[:\s]+([^\n]+)",
        text, re.IGNORECASE
    )
    if match:
        raw = match.group(1).strip()
        # Extract just the date portion  (e.g. "April 27, 2024 (Net 30)" → "April 27, 2024")
        dm = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+\d{1,2},\s+\d{4})", raw, re.IGNORECASE
        )
        if dm:
            return dm.group(1)
        nm = re.search(r"\d{2}[\/\-]\d{2}[\/\-]\d{4}", raw)
        if nm:
            return nm.group(0)
        return raw
    return extract_date(text)


def _extract_due_date(text):
    match = re.search(
        r"(?:due\s*date|payment\s*due(?:\s*date)?|pay\s*by|payment\s*deadline)"
        r"[:\s]+([^\n]+)",
        text, re.IGNORECASE
    )
    if match:
        raw = match.group(1).strip()
        dm = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+\d{1,2},\s+\d{4})", raw, re.IGNORECASE
        )
        if dm:
            return dm.group(1)
        nm = re.search(r"\d{2}[\/\-]\d{2}[\/\-]\d{4}", raw)
        if nm:
            return nm.group(0)
        return raw
    return None


def _extract_total_amount(text):
    """
    Extract the final total amount. Priority:
      1. Specific high-confidence labels (Total Invoice Amount, etc.)
      2. 'TOTAL DUE:' line
      3. 'Total Amount (Subtotal + Total Tax):' line
      4. Generic total labels
      5. 'Total:' plain line (fallback)
    """
    patterns = [
        # Priority 1 — Specific requested labels (supporting pipe | and USD/etc)
        r"(?:total\s*invoice\s*amount|total\s*amount\s*\(usd\)|invoice\s*total)\s*[|:\-]?\s*"
        r"(?:USD|INR|EUR|\$|₹|€)?\s*([\d,]+(?:\.\d{1,2})?)",

        # Priority 2 — TOTAL DUE line
        r"TOTAL\s+DUE\s*[|:\-]?\s*(?:USD|INR|EUR|\$|₹|€)?\s*([\d,]+(?:\.\d{1,2})?)",

        # Priority 3 — Total Amount (Subtotal + Total Tax)
        r"Total\s+Amount\s*\(Subtotal\s*\+\s*Total\s*Tax\)\s*[|:\-]?\s*"
        r"(?:USD|INR|EUR|\$|₹|€)?\s*([\d,]+(?:\.\d{1,2})?)",

        # Priority 4 — Generic labels
        r"(?:total\s*(?:amount|invoice)?|grand\s*total|amount\s*(?:due|payable)|"
        r"net\s*payable)\s*(?:\([A-Z]{3}\))?\s*[|:\-]?\s*"
        r"(?:USD|INR|EUR|\$|₹|€)?\s*([\d,]+(?:\.\d{1,2})?)",

        # Priority 5 — Bare 'Total:' (Multilinear)
        r"^\s*Total\s*[|:\-]?\s*(?:USD|INR|EUR|\$|₹|€)?\s*([\d,]+(?:\.\d{1,2})?)",

        # Priority 6 — Bare currency amount at start of line (often in summary boxes)
        r"^\s*(?:USD|INR|EUR|\$|₹|€)?\s*([\d,]+\.\d{2})\s*$"
    ]

    candidates = []
    for pattern in patterns:
        flags = re.IGNORECASE
        if "^" in pattern:
            flags |= re.MULTILINE
        
        matches = re.finditer(pattern, text, flags)
        for m in matches:
            val_str = m.group(1).replace(",", "")
            try:
                val = float(val_str)
                if val > 0:
                    # Ignore values that look like years (2000-2030) unless they have decimals
                    if 2000 <= val <= 2100 and "." not in m.group(1):
                        continue
                    candidates.append(val)
            except ValueError:
                continue
        
    if candidates:
        return f"{max(candidates):.2f}"

    return None


def _extract_tax(text):
    """
    Extract total tax. Priority:
      1. 'Total Tax:' line
      2. CGST/SGST/IGST/GST Amount labels
      3. Generic 'Tax:' label (plain amount)
    """
    # Priority 1 — Total Tax: USD 36,900.00  or  Total Tax: 36900
    m = re.search(
        r"Total\s+Tax\s*[:\-]?\s*(?:USD|INR|EUR|\$|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).replace(",", "")

    # Priority 2 — CGST/SGST/IGST combined or individual labels
    m = re.search(
        r"(?:cgst|sgst|igst)(?:\s*\([^)]*\))?\s*[:\-]?\s*(?:USD|INR|EUR|\$|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).replace(",", "")

    # Priority 3 — generic tax labels (without currency prefix too)
    m = re.search(
        r"(?:tax\s*(?:amount|total)?|gst\s*(?:amount)?|vat\s*(?:amount)?)"
        r"\s*(?:\([A-Z]{3}\))?\s*[:\-]?\s*(?:USD|INR|EUR|\$|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).replace(",", "")

    return None


def _extract_currency(text):
    # Try labeled: "Currency: USD"
    m = re.search(r"\b(USD|INR|EUR)\b", text)
    return m.group(1) if m else None


def _extract_invoice_number(text):
    """
    Extract invoice number. Handles formats like:
      INV-NC-2024-0101, NC-2024-0101, INV-2024-001
    """
    patterns = [
        # Full labeled: "Invoice No: INV-NC-2024-0101"
        r"(?:invoice\s*(?:no|number|#|num|id|ref)[.:\s#-]*)([A-Z]{2,6}[-/][A-Z]{0,4}[-/]?\d{4}[-/]\d+(?:[-/]\d+)?)",
        r"(?:invoice\s*(?:no|number|#|num|id|ref)[.:\s#-]*)([A-Z]{1,6}[-/\s]?\d{4}[-/\s]\d+)",
        # Simpler numeric IDs like INV-001
        r"(?:invoice\s*(?:no|number|#|num|id|ref)[.:\s#-]*)([A-Z]{1,6}[-]\d{1,10})\b",
        # Standalone ID that looks like INV-NC-2024-0101
        r"\b(INV[-][A-Z]{2,6}[-]\d{4}[-]\d+)\b",
        # NC-2024-0101 style
        r"\b([A-Z]{2,6}[-]\d{4}[-]\d{4,})\b",
        # Generic plain alphanumeric on same line as label
        r"(?:invoice\s*(?:no|number|#)[.:\s]*)([A-Z0-9][A-Z0-9\-/]{3,20})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_po_reference(text):
    """
    Extract PO number. Handles:
      PO-2024-09015, PO 2024 09015, Reference PO: PO-2024-09015
    """
    patterns = [
        # Labeled PO
        r"(?:reference\s+po|po\s*(?:no|number|ref|reference|#))[.:\s#-]*([A-Z0-9]{2,10}(?:[-/\s]?[A-Z0-9]{1,10}){0,5}[-/\s]?\d{4}[-/\s]\d+)\b",
        # Plain PO token
        r"\b(PO[-/\s]?[A-Z0-9]{2,10}(?:[-/\s]?[A-Z0-9]{1,10}){0,5}[-/\s]?\d{4}[-/\s]\d+)\b",
        # Short simple POs
        r"\b(PO[-]\d{3,10})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_grn_reference(text):
    """
    Extract GRN reference number only.
    GRN IDs must start with 'GRN' — never return a PO number as GRN.
    Returns None if no explicit GRN ID found in the document.
    """
    # Direct GRN ID token: 'GRN No: GRN-2024-001' or 'GRN: GRN-001'
    m = re.search(
        r"(?:grn\s*(?:no|number|reference|ref|#)?[.:\s]*)([Gg][Rr][Nn][A-Z0-9\-/]{1,20})\b",
        text, re.IGNORECASE
    )
    if m:
        candidate = m.group(1).strip()
        # Must have at least one digit to be a real ID
        if re.search(r"\d", candidate):
            return candidate

    # Standalone 'GRN-YYYY-NNN' pattern anywhere in text
    m = re.search(r"\b(GRN[-/]\d{4}[-/]\d+)\b", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Not found — return None (GRN required before payment but no GRN ID in invoice yet)
    return None


def _extract_msa_reference(text):
    """Extract MSA reference: MSA-2024-101, Reference MSA: MSA-2024-101"""
    patterns = [
        r"(?:reference\s+msa|msa\s*(?:no|number|ref|reference|id|#))[.:\s#-]*([A-Z0-9]{2,10}[-/\s]?[A-Z0-9]{0,10}[-/\s]?\d{4}[-/\s]\d+)\b",
        r"\b(MSA[-/\s]?[A-Z0-9]{2,10}[-/\s]?[A-Z0-9]{0,10}[-/\s]?\d{4}[-/\s]\d+)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_sow_reference(text):
    """Extract SOW reference: SOW-2024-012, Reference SOW: SOW-2024-012"""
    patterns = [
        r"(?:reference\s+sow|sow\s*(?:no|number|ref|reference|id|#))[.:\s#-]*([A-Z0-9]{2,10}(?:[-/\s]?[A-Z0-9]{1,10}){0,5}[-/\s]?\d{4}[-/\s]\d+)\b",
        r"\b(SOW[-/\s]?[A-Z0-9]{2,10}(?:[-/\s]?[A-Z0-9]{1,10}){0,5}[-/\s]?\d{4}[-/\s]\d+)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_hsn_code(text):
    """
    Extract HSN/SAC code. Handles numeric codes like 998313 and text aliases.
    """
    # Labeled: HSN/SAC 998313  or  HSN Code: 998313
    m = re.search(
        r"(?:hsn[/\\]?sac|hsn\s*code|sac\s*code|hsn|sac)[:\s]*([0-9]{4,8})",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()

    # Standalone numeric code that appears in line item table (6-digit)
    m = re.search(r"\b(9[0-9]{5})\b", text)  # SAC codes start with 9
    if m:
        return m.group(1)

    return None


def _extract_quantity(text):
    """
    Extract quantity. Handles: '1 LS', '1 Lump Sum', '4 units' etc.
    Looks in line items first.
    """
    # Qty column in table: "1 LS"
    m = re.search(r"\b([\d]+)\s+LS\b", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)} LS"

    # "Qty: 4" or "Quantity: 4"
    m = re.search(r"(?:qty|quantity)[:\s]+([\d]+)", text, re.IGNORECASE)
    if m:
        return m.group(1)

    return None


def _extract_unit_price(text):
    """
    Extract unit price (the first / primary line item unit rate).
    Avoids picking up tax rates like '0%' or '9%'.
    Looks for labeled amounts or the first significant number in line items.
    """
    # 'Unit Rate (USD): 52,000.00' or 'Unit Price: 52000.00'
    m = re.search(
        r"(?:unit\s+rate|unit\s+price|price\s+per\s+unit|unit\s+cost|rate)"
        r"(?:\s*\((?:USD|INR|EUR)\))?\s*[:\s]+(?:USD|INR|EUR)?\s*([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).replace(",", "")

    # 'Amount: 52,000.00' labeled line in the line items section
    m = re.search(
        r"(?:^|\n)\s*(?:amount|line\s*amount|item\s*amount)\s*[:\s]+"
        r"(?:USD|INR|EUR)?\s*([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).replace(",", "")

    # Look for first large comma-formatted USD amount (5-6 digit number)
    m = re.search(r"\b(\d{2,3},\d{3}(?:\.\d{2})?)\b", text)
    if m:
        return m.group(1).replace(",", "")

    return None


def _extract_company_code(text):
    """
    Extract GSTIN or company code.
    GSTIN format: 27AACFN5678G1Z3
    """
    # GSTIN (Indian GST number) — 15 chars alphanumeric
    m = re.search(
        r"(?:gstin|gst\s*(?:no|number|in|id))[:\s]*([A-Z0-9]{15})",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()

    # Generic company/entity code
    m = re.search(
        r"(?:company\s*code|entity\s*code|cost\s*center|org\s*code)[:\s]*([A-Z0-9\-]{3,20})",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()

    return None


def _extract_status(text):
    """
    Extract invoice status / payment status.
    Handles: 'All Milestones – Full Invoice', 'Paid', 'Pending' etc.
    """
    # "Status: All Milestones – Full Invoice"
    m = re.search(
        r"(?:status|invoice\s*status|payment\s*status|approval\s*status)"
        r"[:\s]+([^\n]{3,80})",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()

    # "Milestones Billed: M1, M2, M3, M4 (Full Project)"
    m = re.search(
        r"(?:milestones?\s*billed)[:\s]+([^\n]{3,80})",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()

    return None


# Lines that look like PDF section headers — never the real company name
_JUNK_LINE_RE = re.compile(
    r"^\s*(?:[/\\|]+\s*(?:VENDOR|CLIENT|FROM|TO|BILL|SHIP)?\s*$|\(VENDOR\)|\(CLIENT\)|FROM|TO|BILL\s*TO|BILLED\s*BY|"
    r"CLIENT|VENDOR|BILL\s*TO\s*/\s*CLIENT|BILLED\s*BY\s*/\s*VENDOR|BILL\s*TO\s*CLIENT|BILLED\s*BY\s*VENDOR|"
    r"NOT\s*PROVIDED|NOT\s*FOUND|N/A|NA|NULL|NONE)\s*$",
    re.IGNORECASE
)


def _is_junk_line(line: str) -> bool:
    """Return True if the line is a PDF table-header artifact, not a company name."""
    stripped = line.strip()
    if not stripped or len(stripped) < 3:
        return True
    # Matches: '/ VENDOR', '/ CLIENT', '(VENDOR)', 'FROM (VENDOR)', etc.
    if _JUNK_LINE_RE.match(stripped):
        return True
    # Contains nothing but slashes, pipes, dashes — layout noise
    if re.fullmatch(r"[\s/|\-_]+", stripped):
        return True
    return False


def _extract_vendor_name(text):
    """
    Extract vendor name from FROM (VENDOR) section or labeled line.
    Skips PDF-layout junk lines like '/ VENDOR' that appear between the
    section header and the actual company name.
    """
    # 'FROM (VENDOR)' / 'BILLED BY' block
    m = re.search(r"(?:FROM\s*\(VENDOR\)|FROM:|VENDOR:|BILLED\s*BY\s*/\s*VENDOR|BILLED\s*BY(?:\s*/\s*VENDOR)?)", text, re.IGNORECASE)
    if m:
        rest = text[m.end():]
        # Split and skip the rest of the current line if it's just layout junk
        lines_to_check = rest.split("\n")
        if lines_to_check and _is_junk_line(lines_to_check[0]):
            lines_to_check = lines_to_check[1:]
        
        for line in lines_to_check[:6]:
            candidate = line.strip()
            candidate = re.sub(r"^[|/\s]+", "", candidate)
            candidate = re.sub(r"[|/\s]+$", "", candidate)
            if candidate and not _is_junk_line(candidate):
                # If the line has a wide gap (OCR merged two columns), take the relevant part
                if "  " in candidate:
                    parts = [p.strip() for p in re.split(r"\s{2,}", candidate) if p.strip()]
                    if parts:
                        return parts[-1] # Vendor is usually on the right
                return candidate

    # 'Vendor Name: ...' label (supporting | and :)
    m = re.search(
        r"(?:vendor\s*(?:name)?|service\s*provider|supplier\s*(?:name)?|billed?\s*(?:by|from))\s*[|:\-]\s*([^|\n]{3,80})",
        text, re.IGNORECASE
    )
    if m:
        val = m.group(1).strip()
        if not _is_junk_line(val):
            return val

    # Fallback: Look for company names in the first 10 lines
    lines = text.split("\n")[:10]
    for line in lines:
        candidate = line.strip()
        if candidate and len(candidate) > 5 and not _is_junk_line(candidate):
            if any(x in candidate.lower() for x in ["corp", "inc", "ltd", "pvt", "limited", "systems", "solutions", "services"]):
                return candidate

    return None


def _extract_client_name(text):
    """
    Extract client/buyer name from TO (CLIENT) block or labeled line.
    Skips PDF-layout junk lines like '/ CLIENT'.
    """
    # 'TO (CLIENT)' / 'BILL TO' block
    m = re.search(r"(?:TO\s*\(CLIENT\)|TO:|CLIENT:|BILL\s*TO\s*/\s*CLIENT|BILL\s*TO(?:\s*/\s*CLIENT)?)", text, re.IGNORECASE)
    if m:
        rest = text[m.end():]
        # Split and skip the rest of the current line if it's just layout junk
        lines_to_check = rest.split("\n")
        if lines_to_check and _is_junk_line(lines_to_check[0]):
            lines_to_check = lines_to_check[1:]

        for line in lines_to_check[:6]:
            candidate = line.strip()
            candidate = re.sub(r"^[|/\s]+", "", candidate)
            candidate = re.sub(r"[|/\s]+$", "", candidate)
            if candidate and not _is_junk_line(candidate):
                # If the line has a wide gap (OCR merged two columns), take the first part
                if "  " in candidate:
                    parts = [p.strip() for p in re.split(r"\s{2,}", candidate) if p.strip()]
                    if parts:
                        return parts[0] # Client is usually on the left
                return candidate

    # 'Bill To:' / 'Billed To:' labeled line (supporting | and :)
    m = re.search(
        r"(?:bill(?:ed)?\s*to|client\s*(?:name)?|customer\s*(?:name)?|buyer|sold\s*to|ship\s*to)\s*[|:\-]\s*([^|\n]{3,80})",
        text, re.IGNORECASE
    )
    if m:
        val = m.group(1).strip()
        if not _is_junk_line(val):
            return val

    return None


def _extract_bank_details(text):
    """
    Extract bank / payment details section.
    Returns a multi-line string with account info, or None.
    """
    # Find section after 'Bank Details' / 'Payment Details' header
    m = re.search(
        r"(?:bank\s*details?|payment\s*details?|remittance\s*details?|wire\s*transfer)"
        r"[:\s]*\n((?:.*\n){1,8})",
        text, re.IGNORECASE
    )
    if m:
        block = m.group(1).strip()
        if block:
            return block[:600]

    # Inline patterns: 'Account No: 1234567890'
    parts = []
    for pat, label in [
        (r"(?:account\s*(?:no|number|#))[:\s]+([^\n]{4,40})", "Account No"),
        (r"(?:bank\s*name)[:\s]+([^\n]{3,60})",               "Bank"),
        (r"(?:ifsc\s*(?:code)?)[:\s]+([A-Z0-9]{8,12})",       "IFSC"),
        (r"(?:swift\s*(?:code)?)[:\s]+([A-Z0-9]{8,11})",      "SWIFT"),
        (r"(?:routing\s*(?:number)?)[:\s]+([\d]{9})",         "Routing"),
    ]:
        hit = re.search(pat, text, re.IGNORECASE)
        if hit:
            parts.append(f"{label}: {hit.group(1).strip()}")

    return "\n".join(parts) if parts else None


def _extract_tax_breakup(text):
    """
    Extract tax breakdown details (CGST / SGST / IGST rates and amounts).
    Returns a formatted string or None.
    """
    parts = []

    # Look for CGST / SGST / IGST lines
    for tax_type in ["CGST", "SGST", "IGST", "GST"]:
        # 'CGST (9%): USD 18,450.00'  or  'CGST @ 9% = 18450'
        m = re.search(
            rf"{tax_type}\s*(?:[@(]\s*([\d.]+)\s*%[)\s]*)?[:\s=]+"
            r"(?:USD|INR|EUR)?\s*([\d,]+(?:\.\d{{1,2}})?)",
            text, re.IGNORECASE
        )
        if m:
            rate   = m.group(1)
            amount = m.group(2).replace(",", "")
            entry  = f"{tax_type.upper()}"
            if rate:
                entry += f" ({rate}%)"
            entry += f": {amount}"
            parts.append(entry)

    # Generic 'Tax Rate: 18%'  or  'Tax %: 15'
    m = re.search(
        r"(?:tax\s*(?:rate|%|percent))[:\s]+([\d.]+\s*%?)",
        text, re.IGNORECASE
    )
    if m and not parts:
        parts.append(f"Tax Rate: {m.group(1).strip()}")

    # Total tax line as fallback summary
    m = re.search(
        r"Total\s+Tax[:\s]+(?:USD|INR|EUR)?\s*([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE
    )
    if m:
        parts.append(f"Total Tax: {m.group(1).replace(',', '')}")

    return "\n".join(parts) if parts else None


# Fields handled by dedicated extractors — skip in generic loop
_SKIP_IN_GENERIC = {
    "invoice_date", "due_date", "start_date",
    "total_amount", "tax", "currency",
    "invoice_number", "po_reference_number", "grn_reference",
    "hsn_code", "quantity", "unit_price", "company_code",
    "status", "vendor_name", "client_name",
}


# ===============================
# MAIN FUNCTION
# ===============================
def extract_with_rules(text):
    lines = text.split("\n")
    data = {}

    # ---- Dedicated / special extractions ----
    data["invoice_date"]         = _extract_invoice_date(text)
    data["due_date"]             = _extract_due_date(text)
    data["start_date"]           = extract_date(text)          # MSA legacy
    data["total_amount"]         = _extract_total_amount(text)
    data["tax"]                  = _extract_tax(text)
    data["currency"]             = _extract_currency(text)
    data["invoice_number"]       = _extract_invoice_number(text)
    data["po_reference_number"]  = _extract_po_reference(text)
    data["grn_reference"]        = _extract_grn_reference(text)
    data["hsn_code"]             = _extract_hsn_code(text)
    data["quantity"]             = _extract_quantity(text)
    data["unit_price"]           = _extract_unit_price(text)
    data["company_code"]         = _extract_company_code(text)
    data["status"]               = _extract_status(text)
    data["vendor_name"]          = _extract_vendor_name(text)
    data["client_name"]          = _extract_client_name(text)

    # MSA / SOW references (bonus fields used by decision agent)
    data["msa_id"]  = _extract_msa_reference(text)
    data["sow_id"]  = _extract_sow_reference(text)

    # MSA legacy fields
    created_match = re.search(r"Created By[:\s]+(.+)", text, re.IGNORECASE)
    data["created_by"] = created_match.group(1).strip() if created_match else None

    termination = extract_section(text, "termination")
    data["termination_clause"] = termination[:400] if termination else None

    # ---- Unstructured sections ----
    data.update(extract_unstructured_sections(text))

    # Dedicated unstructured extractors (override alias-based results if better)
    bank   = _extract_bank_details(text)
    taxbkp = _extract_tax_breakup(text)
    if bank:
        data["bank_details"] = bank
    if taxbkp:
        data["tax_breakup"] = taxbkp

    # ---- Generic alias-based extraction (for any field not yet filled) ----
    for field, aliases in FIELD_ALIASES.items():

        if field in _SKIP_IN_GENERIC:
            continue

        # Skip if already extracted by a dedicated extractor
        if data.get(field):
            continue

        value = None

        for i, line in enumerate(lines):
            norm_line = normalize(line)

            for alias in aliases:

                # Inline match:  "Invoice No: INV-2024-001"
                match = re.search(rf"{re.escape(alias)}[:\-]?\s*(.+)", norm_line)
                if match:
                    candidate = match.group(1).strip()
                    if is_valid_value(field, candidate):
                        value = candidate
                        break

                # Next-line match (label on one line, value on the next)
                if alias in norm_line:
                    for j in range(i + 1, min(i + 4, len(lines))):
                        candidate = lines[j].strip()
                        if is_valid_value(field, candidate):
                            value = candidate
                            break

                if value:
                    break

            if value:
                break

        data[field] = value

    return data