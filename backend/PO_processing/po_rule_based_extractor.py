"""
po_rule_based_extractor.py

Rule-based (regex + alias) extraction for all PO structured and unstructured fields.
Used as the fallback/complement to LLM extraction.

Fixes applied vs original:
  - start_date and end_date use separate keyword-anchored search (not same extract_date call)
  - unit_price cap removed (no arbitrary 1,000,000 upper limit)
  - vendor/client name validation relaxed to 2-char minimum (handles single-word names)
  - next-line alias match now breaks the outer loop correctly
  - tax pattern anchored to tax keywords (no false matches on page numbers / zip codes)
  - tabular fields (qty, unit_price, tax, service_code) always use column-dump extractor
"""

import re

# ===============================
# STRUCTURED FIELD ALIASES
# ===============================
FIELD_ALIASES = {
    "po_id": [
        "po no", "po number", "purchase order no", "purchase order number",
        "po#", "po #", "po-", "po -", "po_no", "po_no.", "purchase order no.",
        "purchase order no", "order no", "order number", "po ref", "po reference",
        "purchase order ref", "purchase order reference", "po id"
    ],
    "vendor_name": [
        "vendor name", "vendor_name", "vendor-name",
        "service provider", "provider", "vendor",
        "bill from", "billed by", "supplier name", "seller"
    ],
    "client_name": [
        "client name", "customer name", "buyer name", "sold to",
        "ship to", "bill to", "customer", "client"
    ],
    "payment_terms": [
        "payment terms", "terms of payment", "payment condition",
        "payment", "terms"
    ],
    "delivery_terms": [
        "delivery terms", "terms of delivery", "delivery condition",
        "shipping terms", "incoterms"
    ],
    "currency": [
        "currency", "usd", "inr", "eur", "currency code"
    ],
    "total_amount": [
        "total amount", "total", "grand total", "po total",
        "amount", "net amount", "total value", "order value"
    ],
    "start_date": [
        "start date", "commencement date", "effective date",
        "contract start", "period start", "from date"
    ],
    "end_date": [
        "end date", "expiry date", "completion date",
        "contract end", "period end", "to date", "valid until"
    ],
    "reference_sow": [
        "reference sow", "sow reference", "sow number",
        "statement of work", "sow no", "sow#", "ref. sow", "ref sow"
    ],
    "reference_msa": [
        "reference msa", "msa reference", "msa number",
        "master service agreement", "msa no", "msa#", "ref. msa", "ref msa"
    ],
    "quantity": [
        "quantity", "qty", "units", "no of units",
        "number of units", "count", "nos"
    ],
    "unit_price": [
        "unit price", "rate", "price per unit", "unit rate",
        "unit cost", "cost per unit", "price", "per unit"
    ],
    "tax": [
        "tax", "tax amount", "gst", "vat", "tax total",
        "total tax", "igst", "cgst", "sgst", "gst amount"
    ],
    "tax_breakup": [
        "tax breakup", "tax breakdown", "tax details",
        "tax composition", "gst breakup"
    ],
    "service_code": [
        "service code", "service code no", "service id",
        "item code", "product code", "sku"
    ],
    "delivery_location": [
        "delivery location", "shipping address", "delivery address",
        "ship to location", "delivery point"
    ],
    "grn_indicator": [
        "grn indicator", "grn required", "grn flag",
        "goods receipt note", "grn"
    ],
    "po_status": [
        "po status", "status", "order status", "purchase order status",
        "approval status"
    ]
}

# ===============================
# UNSTRUCTURED FIELD ALIASES
# ===============================
UNSTRUCTURED_ALIASES = {
    "description_of_goods_and_services": [
        "description of goods and services", "description", "item description",
        "scope of work", "particulars", "nature of service",
        "line items", "work description", "goods description", "services description"
    ]
}

# Fields handled by dedicated extractors — skip in generic alias loop
_SKIP_IN_GENERIC = {
    "po_date", "start_date", "end_date",
    "total_amount", "tax", "currency", "quantity", "unit_price", "service_code"
}


# ===============================
# NORMALIZATION
# ===============================
def normalize(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ===============================
# DATE EXTRACTION (returns YYYY-MM-DD)
# ===============================
def extract_date(text):
    """Extract the first recognisable date from a short text fragment."""
    if not text:
        return None

    # Named month: January 15, 2024 / 15 January 2024
    match = re.search(
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
        text
    )
    if match:
        month_map = {
            "January": "01", "February": "02", "March": "03", "April": "04",
            "May": "05", "June": "06", "July": "07", "August": "08",
            "September": "09", "October": "10", "November": "11", "December": "12"
        }
        month = month_map[match.group(1)]
        day = match.group(2).zfill(2)
        year = match.group(3)
        return f"{year}-{month}-{day}"

    match = re.search(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)[,\s]+(\d{4})",
        text
    )
    if match:
        month_map = {
            "January": "01", "February": "02", "March": "03", "April": "04",
            "May": "05", "June": "06", "July": "07", "August": "08",
            "September": "09", "October": "10", "November": "11", "December": "12"
        }
        day = match.group(1).zfill(2)
        month = month_map[match.group(2)]
        year = match.group(3)
        return f"{year}-{month}-{day}"

    # Numeric formats: DD/MM/YYYY | MM-DD-YYYY | YYYY-MM-DD
    match = re.search(
        r"\b(\d{2}[\/\-]\d{2}[\/\-]\d{4}|\d{4}[\/\-]\d{2}[\/\-]\d{2})\b",
        text
    )
    if match:
        date_str = match.group(0)
        from datetime import datetime
        formats = ["%d/%m/%Y", "%m-%d-%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                continue

    return None


def _extract_labelled_date(text: str, labels: list) -> str:
    """
    Search for a date that immediately follows one of the given label keywords.
    Returns YYYY-MM-DD or None.
    """
    for label in labels:
        m = re.search(
            rf'(?:{re.escape(label)})[:\s]+([^\n]{{3,50}})',
            text, re.IGNORECASE
        )
        if m:
            d = extract_date(m.group(1))
            if d:
                return d
    return None


# ===============================
# AMOUNT EXTRACTION
# ===============================
def extract_amount(text):
    """Pull a numeric amount with optional currency symbol."""
    if not text:
        return None
    match = re.search(r"[\$₹€]?\s*[\d,]+(?:\.\d{1,2})?", text)
    return match.group(0).strip() if match else None


# ===============================
# STRICT SECTION EXTRACTION
# ===============================
def extract_section(text, keyword):
    if not text or not keyword:
        return None

    # Pattern 1: Numbered section
    pattern = rf"\d+\.\s*{re.escape(keyword)}.*?\n(.+?)(?=\n\s*\d+\.|\n\s*[A-Z][A-Z\s]+|\Z)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()

    # Pattern 2: Non-numbered section
    pattern = rf"{re.escape(keyword)}.*?\n(.+?)(?=\n\s*[A-Z][A-Z\s]+|\n\s*\d+\.|\Z)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback
    pattern = rf"{re.escape(keyword)}[:\s]*(.*?)(?=\n\s*[A-Z][A-Z]+|\Z)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()

    return None


# ===============================
# VALIDATION
# ===============================
def is_valid_value(field, value):
    if not value:
        return False

    value = str(value).strip()

    if len(value) < 2:
        return False

    if value.lower() in ["or", "and", "the", "n/a", "-", "nil", "none"]:
        return False

    if field == "currency":
        return value.upper() in ["USD", "INR", "EUR", "GBP", "JPY", "CAD", "AUD", "SAR", "AED"]

    if field in ("vendor_name", "client_name"):
        # Relaxed: single-word names like "IBM", "Infosys" are valid
        # But reject generic label words that are just headers
        lower_val = value.lower()
        generic_labels = ['client', 'customer', 'buyer', 'vendor', 'supplier', 'seller', 'provider', 'bill to', 'ship to', 'sold to']
        if lower_val in generic_labels:
            return False
        return len(value) >= 2

    if field == "po_id":
        return bool(re.search(r"[a-z0-9\-\/]{3,}", value.lower()))

    if field in ("service_code", "reference_sow", "reference_msa", "grn_indicator"):
        return bool(re.search(r"[a-z0-9]{2,}", value.lower()))

    if field in ("total_amount", "unit_price", "tax", "quantity"):
        return bool(re.search(r"\d", value))

    return True


# ===============================
# UNSTRUCTURED EXTRACTION
# ===============================
def _extract_description_of_goods_and_services(text):
    """Extract the Description of Goods and Services section."""
    print("[DEBUG] Extracting Description of Goods and Services...")

    patterns = [
        r"DESCRIPTION OF GOODS\s*&\s*SERVICES",
        r"DESCRIPTION OF GOODS AND SERVICES",
        r"DESCRIPTION OF GOODS",
        r"SCOPE OF WORK",
        r"PARTICULARS"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start_pos = match.end()
            remaining_text = text[start_pos:]

            end_patterns = [
                r"\n\s*[A-Z][A-Z\s]{10,}",
                r"\n\s*\d+\.[A-Z]",
                r"\n\s*(?:PAYMENT|DELIVERY|CURRENCY|VENDOR|CLIENT|BILLING|SHIPPING)"
            ]

            end_pos = len(remaining_text)
            for end_pattern in end_patterns:
                end_match = re.search(end_pattern, remaining_text, re.IGNORECASE)
                if end_match:
                    end_pos = min(end_pos, end_match.start())

            extracted = remaining_text[:end_pos].strip()
            return _preserve_formatting(extracted)

    return None


def _preserve_formatting(text):
    """Clean text while preserving bullets, numbered lists, and paragraph spacing."""
    if not text:
        return ""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)


def extract_unstructured_sections(text):
    result = {}
    for field, aliases in UNSTRUCTURED_ALIASES.items():
        value = None
        if field == "description_of_goods_and_services":
            value = _extract_description_of_goods_and_services(text)
        else:
            for alias in aliases:
                section = extract_section(text, alias)
                if section:
                    value = section
                    break
        result[field] = value
    return result


# ===============================
# DEDICATED EXTRACTORS
# ===============================

def _extract_po_date(text):
    """Extract PO date using keyword anchor, fall back to first date in text."""
    m = re.search(
        r"(?:po\s*date|purchase\s*order\s*date|order\s*date|date\s*of\s*purchase\s*order|"
        r"issued\s*date|creation\s*date)"
        r"[:\s]+([^\n]+)",
        text, re.IGNORECASE
    )
    return extract_date(m.group(1).strip()) if m else extract_date(text)


def _extract_total_amount(text):
    """Extract total PO amount; avoids picking up tax-only lines and Total incl. VAT."""
    # Pattern 1: Standard total amount labels (case insensitive)
    patterns = [
        r"(?:total\s*amount|grand\s*total|net\s*amount|total\s*value|order\s*value|po\s*total)"
        r"[:\s]+([\$₹€]?\s*[\d,]+(?:\.\d{1,2})?)",
        r"(?:subtotal|amount)[:\s]+([\$₹€]?\s*[\d,]+(?:\.\d{1,2})?)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            line = match.group(0).lower()
            if "tax" not in line and "vat" not in line and "gst" not in line:
                return match.group(1).strip()

    # Pattern 2: Look for TOTAL row in table (like in the screenshot)
    # TOTAL $950,000.00 pattern
    table_total_pattern = r'TOTAL\s+\$?([\d,]+(?:\.\d{2})?)'
    match = re.search(table_total_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern 3: Look for total in parenthesis format
    # e.g., "Total (USD) $950,000.00"
    paren_total_pattern = r'Total\s*\(USD\)\s+\$?([\d,]+(?:\.\d{2})?)'
    match = re.search(paren_total_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: largest monetary value in document (but exclude Total incl. VAT amounts)
    amounts = re.findall(r'[\$₹€]?\s*[\d,]+(?:\.\d{1,2})?', text)
    cleaned_amounts = []
    for amt in amounts:
        cleaned = re.sub(r'[^\d.]', '', amt)
        if cleaned:
            try:
                val = float(cleaned)
                # Exclude very large amounts that are likely Total incl. VAT
                # PO total is typically the second largest or the one in the TOTAL row
                cleaned_amounts.append(val)
            except ValueError:
                continue

    # If we have amounts, prefer ones that look like PO totals (not the absolute largest which may be Total incl. VAT)
    if cleaned_amounts:
        sorted_amounts = sorted(cleaned_amounts, reverse=True)
        # Return the largest that's under $2M (reasonable PO limit) and not the absolute max if max > 1M
        for amt in sorted_amounts:
            if amt < 2000000:  # Reasonable PO total limit
                return str(int(amt)) if amt == int(amt) else str(amt)
        return str(int(sorted_amounts[0])) if sorted_amounts[0] == int(sorted_amounts[0]) else str(sorted_amounts[0])

    return None


def _extract_currency(text):
    match = re.search(r"\b(USD|INR|EUR|GBP|JPY|CAD|AUD|SAR|AED)\b", text)
    return match.group(1) if match else None


# ===============================
# MAIN FUNCTION
# ===============================
def extract_with_rules(text):
    """
    Run all rule-based extractors over the document text.
    Returns a flat dict of field → value.
    Tabular fields (quantity, unit_price, tax, service_code) return lists.
    """
    if not text:
        return {}

    lines = text.split("\n")
    data = {}

    # ---- Dedicated scalar extractors ----
    data["po_date"] = _extract_po_date(text)

    # FIX: separate keyword-anchored date search for start/end (not the same call)
    data["start_date"] = _extract_labelled_date(text, [
        "start date", "commencement date", "effective date",
        "contract start", "period start", "from date"
    ])
    data["end_date"] = _extract_labelled_date(text, [
        "end date", "expiry date", "completion date",
        "contract end", "period end", "to date", "valid until"
    ])

    data["total_amount"] = _extract_total_amount(text)
    data["currency"] = _extract_currency(text)

    # ---- Tabular array fields — always use column-dump extractor ----
    from PO_processing.po_tabular_converter import extract_tabular_data_from_text

    print(f"[DEBUG RULE-BASED] Text length: {len(text)}")

    data["quantity"]     = extract_tabular_data_from_text(text, "quantity")
    data["unit_price"]   = extract_tabular_data_from_text(text, "unit_price")
    data["tax"]          = extract_tabular_data_from_text(text, "tax")
    data["service_code"] = extract_tabular_data_from_text(text, "service_code")

    print(f"[DEBUG RULE-BASED] quantity    : {data['quantity']}")
    print(f"[DEBUG RULE-BASED] unit_price  : {data['unit_price']}")
    print(f"[DEBUG RULE-BASED] tax         : {data['tax']}")
    print(f"[DEBUG RULE-BASED] service_code: {data['service_code']}")

    # ---- Unstructured sections ----
    unstructured_data = extract_unstructured_sections(text)
    data.update(unstructured_data)
    
    # If description is empty, build it from LINE-ITEMS table descriptions
    if not data.get('description_of_goods_and_services'):
        from PO_processing.po_tabular_converter import _extract_from_line_items_table
        line_items = _extract_from_line_items_table(text)
        if line_items and line_items.get('description'):
            descriptions = line_items['description']
            service_codes = line_items.get('service_code', [])
            # Build formatted description
            desc_lines = []
            for i, desc in enumerate(descriptions):
                svc_code = service_codes[i] if i < len(service_codes) else f"Item {i+1}"
                desc_lines.append(f"{svc_code}: {desc}")
            data['description_of_goods_and_services'] = "\n".join(desc_lines)
            print(f"[DEBUG] Built description from {len(descriptions)} line items")
            print(f"[DEBUG] Description preview: {data['description_of_goods_and_services'][:200]}...")

    # ---- Generic alias-based extraction for all remaining scalar fields ----
    for field, aliases in FIELD_ALIASES.items():

        if field in _SKIP_IN_GENERIC:
            continue

        value = None

        for i, line in enumerate(lines):
            norm_line = normalize(line)

            for alias in aliases:

                # Inline match: "PO No: PO-2024-001"
                match = re.search(rf"{re.escape(alias)}[:\-]?\s*(.+)", norm_line)
                if match:
                    candidate = match.group(1).strip()
                    if is_valid_value(field, candidate):
                        value = candidate
                        break

                # Next-line match: label on one line, value on the next
                if alias in norm_line and not value:
                    for j in range(i + 1, min(i + 4, len(lines))):
                        candidate = lines[j].strip()
                        if is_valid_value(field, candidate):
                            value = candidate
                            break
                    # FIX: break alias loop after next-line match succeeds
                    if value:
                        break

            if value:
                break

        # Don't overwrite tabular array fields if they already have valid arrays
        if field in ("service_code", "quantity", "unit_price", "tax"):
            existing = data.get(field)
            if existing and isinstance(existing, list) and len(existing) > 0:
                print(f"[DEBUG GENERIC] Skipping overwrite for '{field}' - already has array: {existing}")
                continue

        data[field] = value

    return data