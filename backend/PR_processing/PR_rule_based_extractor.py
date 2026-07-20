import re
import json

# ===============================
# STRUCTURED FIELD ALIASES
# ===============================
FIELD_ALIASES = {
    "pr_id": [
        "pr id",
        "pr_id",
        "pr-id",
        "purchase requisition id",
        "purchase requisition number",
        "requisition id",
        "requisition number"
    ],

    "requested_by": [
        "requested by",
        "requestor",
        "raised by",
        "created by",
        "prepared by"
    ],

    "department": [
        "department",
        "dept",
        "business unit",
        "cost center department"
    ],

    "vendor_name": [
        "vendor name",
        "vendor_name",
        "vendor-name",
        "supplier name",
        "supplier",
        "vendor"
    ],

    "budget_code": [
        "budget code",
        "cost center",
        "cost centre",
        "gl code",
        "account code"
    ],

    "priority": [
        "priority",
        "urgency",
        "request priority"
    ],

    "total_amount": [
        "total amount",
        "amount",
        "total value",
        "estimated value",
        "pr value"
    ],

    "currency": [
        "currency",
        "usd",
        "inr",
        "eur"
    ],

    "request_date": [
        "request date",
        "requisition date",
        "pr date",
        "date of request"
    ],

    "required_date": [
        "required date",
        "need by date",
        "delivery date",
        "expected date"
    ],

    "reference_sow_number": [
        "sow number",
        "sow id",
        "statement of work",
        "sow reference"
    ],

    "reference_msa_number": [
        "msa number",
        "msa id",
        "master service agreement",
        "msa reference"
    ],

    "approval_status": [
        "approval status",
        "status",
        "pr status",
        "approval"
    ],

    "service_code": [
        "service code",
        "item code",
        "product code",
        "sku"
    ],

    "purchasing_group": [
        "purchasing group",
        "buyer group",
        "procurement group",
        "purchase group"
    ]
}

# ===============================
# UNSTRUCTURED FIELD ALIASES
# ===============================
UNSTRUCTURED_ALIASES = {
    "quantity": [
        "quantity",
        "qty",
        "units",
        "number of units",
        "item quantity"
    ],

    "location": [
        "location",
        "delivery location",
        "ship to",
        "delivery address",
        "site"
    ],

    "description": [
        "description",
        "description of goods",
        "description of services",
        "goods description",
        "service description",
        "item description",
        "scope of work"
    ]
}

# ===============================
# CURRENCY SYMBOL MAP
# ===============================
CURRENCY_SYMBOL_MAP = {
    "$": "USD",
    "₹": "INR",
    "€": "EUR",
    "£": "GBP"
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
# CLEAN VALUE
# ===============================
def clean_value(field, value):
    if not value:
        return value

    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value)

    if field == "pr_id":
        value = re.sub(r"\s*date\s*:.*", "", value, flags=re.IGNORECASE)

    if field == "description":
        stop_words = [
            "APPROVAL", "VENDOR", "BUDGET", "PAYMENT",
            "PURCHASING GROUP", "PRIORITY", "LOCATION", "SERVICE CODE"
        ]
        for stop_word in stop_words:
            value = re.split(rf"\b{stop_word}\b", value, flags=re.IGNORECASE)[0]

    if field == "total_amount":
        value = re.sub(r"[₹$€£]", "", value)
        value = re.sub(r"\b(USD|INR|EUR|GBP|Amount|Total)\b", "", value, flags=re.IGNORECASE)
        value = value.replace(",", "")

    return value.strip()


# ===============================
# DATE EXTRACTION
# ===============================
def extract_date(text):
    match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
        r"|"
        r"\d{2}[\/\-]\d{2}[\/\-]\d{4}"
        r"|"
        r"\d{4}[\/\-]\d{2}[\/\-]\d{2}",
        text
    )
    return match.group(0) if match else None


# ===============================
# STRICT SECTION EXTRACTION
# ===============================
def extract_section(text, keyword):
    pattern = rf"""
    (?:
        \n|^
    )
    \s*
    (?:\d+\.?\s*)?
    {re.escape(keyword)}
    [^\n]*
    \n
    (.*?)
    (?=
        \n\s*(?:\d+\.?\s+[A-Z][A-Z\s]{{2,}})
        |
        \n[A-Z][A-Z\s]{{4,}}
        |
        \Z
    )
    """
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.VERBOSE)
    if match:
        section = match.group(1)
        section = re.sub(r"\s+", " ", section)
        return section[:1000].strip()
    return None


# ===============================
# VALIDATION
# ===============================
def is_valid_value(field, value):
    if not value:
        return False

    value = value.strip()

    if len(value) < 3:
        return False

    if value.lower() in ["or", "and", "the"]:
        return False

    if field == "pr_id":
        return bool(re.search(r"[A-Za-z0-9\-]{4,}", value))

    if field == "currency":
        return value.upper() in ["USD", "INR", "EUR", "GBP"]

    if field == "vendor_name":
        return len(value.split()) >= 2

    if field == "total_amount":
        return bool(re.search(r"\d+(\.\d+)?", value))

    if field == "priority":
        return value.capitalize() in ["High", "Medium", "Low"]

    if field == "approval_status":
        return value.capitalize() in ["Pending", "Approved", "Rejected"]

    return True


# ===============================
# FIX 1: CURRENCY EXTRACTION
# ===============================
def extract_currency(text):
    word_match = re.search(r"\b(USD|INR|EUR|GBP)\b", text, re.IGNORECASE)
    if word_match:
        return word_match.group(1).upper()

    symbol_match = re.search(r"[₹$€£]", text)
    if symbol_match:
        return CURRENCY_SYMBOL_MAP.get(symbol_match.group(0))

    return None


# ===============================
# FIX 2: REQUESTED BY EXTRACTION
# ===============================
def extract_requested_by(text):
    match = re.search(
        r"(?:Requested By|Requestor|Raised By|Prepared By|Created By)\s*[:\-]?\s*(.+)",
        text,
        re.IGNORECASE
    )
    if not match:
        return None, None

    raw = match.group(1).strip()

    # Remove anything after "Title:", "Designation:", "Dept:" on the same line
    raw = re.sub(r"\s+(?:Title|Designation|Dept|Department)\s*:.*", "", raw, flags=re.IGNORECASE)

    # Split on 2+ spaces, tab, or newline — name is always first part
    parts = re.split(r"\s{2,}|\n|\t", raw)
    name = parts[0].strip() if parts else raw
    title = parts[1].strip() if len(parts) > 1 else None

    # Final safety: if name still has a colon, it leaked a label — take only part before it
    if ":" in name:
        name = name.split(":")[0].strip()

    return name, title


# ===============================
# FIX 3: REQUIRED DATE EXTRACTION
# ===============================
def extract_required_date(text):
    match = re.search(
        r"(?:Required By|Need By Date|Delivery Date|Required Date|Expected Date)\s*[:\-]?\s*(.{5,50})",
        text,
        re.IGNORECASE
    )
    if match:
        return extract_date(match.group(1))
    return None


# ===============================
# FIX 4: QUANTITY EXTRACTION
# Handles the actual document table structure:
# | # | Service Code | Description | Qty | UoM | Unit Price | Total | Milestone |
# ===============================
def extract_quantity(text):
    quantity_dict = {}

    # Strategy 1: Full line-item table row
    # Pattern: | row_num | SVC-CODE | Description text | qty | UoM | ...
    line_item_matches = re.findall(
        r"\|\s*\d+\s*\|\s*([A-Z]{2,6}-[A-Z0-9]{1,6}-[0-9]{2,4})\s*\|([^|]{5,120})\|\s*(\d+)\s*\|\s*(?:LS|EA|HR|PC|NOS|PCS|UNIT|hrs?)",
        text,
        re.IGNORECASE
    )
    for code, desc, qty in line_item_matches:
        # Use the description up to the first em-dash or long hyphen as label
        label = re.split(r"\s*[–—]\s*|\s*-\s*(?=[A-Z])", desc.strip())[0]
        label = re.sub(r"\*+", "", label).strip()
        label = re.sub(r"\s+", " ", label)[:80].strip()
        if label and len(label) > 2:
            quantity_dict[label] = int(qty)

    if quantity_dict:
        return quantity_dict

    # Strategy 2: Description | qty | UoM pattern (no service code column)
    table_matches = re.findall(
        r"\|\s*\*{0,2}([A-Za-z][^|*\n]{5,80}?)\*{0,2}\s*\|\s*(\d+)\s*\|\s*(?:LS|EA|HR|PC|NOS|PCS|UNIT|hrs?)",
        text,
        re.IGNORECASE
    )
    for label, qty in table_matches:
        label = label.strip()
        skip_words = ["quantity", "qty", "amount", "total", "priority",
                      "status", "department", "vendor", "service code",
                      "description", "unit price", "#"]
        if len(label) > 2 and not any(sw in label.lower() for sw in skip_words):
            quantity_dict[label] = int(qty)

    if quantity_dict:
        return quantity_dict

    # Strategy 3: Simple "Label | qty |" table
    simple_table = re.findall(r"([A-Za-z][^\n\r|]{3,60}?)\s*\|\s*(\d+)\s*\|", text)
    for label, qty in simple_table:
        label = label.strip().strip("-:*").strip()
        if len(label) > 2:
            quantity_dict[label] = int(qty)

    if quantity_dict:
        return quantity_dict

    # Strategy 4: Inline "Label : 10 units"
    inline_matches = re.findall(
        r"([A-Za-z][^\n\r:\-]{3,60}?)\s*[:\-]\s*(\d+)\s*(?:units?|pcs?|nos?|hrs?|hours?)?",
        text,
        re.IGNORECASE
    )
    for label, qty in inline_matches:
        label = label.strip().strip("-:").strip()
        skip_words = ["quantity", "qty", "amount", "total",
                      "priority", "status", "department", "vendor"]
        if len(label) > 2 and label.lower() not in skip_words:
            quantity_dict[label] = int(qty)

    if quantity_dict:
        return quantity_dict

    # Strategy 5: Fallback keyword + number
    for alias in UNSTRUCTURED_ALIASES["quantity"]:
        matches = re.findall(
            rf"{re.escape(alias)}[:\-]?\s*(\d+[\.\d]*)",
            text,
            re.IGNORECASE
        )
        if matches:
            for idx, qty in enumerate(matches, start=1):
                quantity_dict[f"item_{idx}"] = float(qty)
            break

    return quantity_dict


# ===============================
# FIX 5: SERVICE CODE EXTRACTION
# Handles table column format: | SVC-DM-001 |
# Rejects section heading text
# ===============================
def extract_service_code(text):
    """
    Extracts the FIRST valid service/item/product code from the document.
    Targets pipe-delimited table cells.
    Rejects long descriptive/sentence text.
    """

    # Strategy 1: Table cell — | SVC-DM-001 | (strict code format)
    # Matches: SVC-DM-001, IT-MIG-01, SKU-12345, SVC-001
    table_code_match = re.search(
        r"\|\s*([A-Z]{2,6}-[A-Z0-9]{1,8}-[0-9]{2,4})\s*\|",
        text,
        re.IGNORECASE
    )
    if table_code_match:
        return table_code_match.group(1).strip().upper()

    # Strategy 2: Labeled field — "Service Code: SVC-001"
    # Only grabs a short single-token alphanumeric code
    labeled_match = re.search(
        r"(?:service\s*code|item\s*code|product\s*code|sku)\s*[:\-]\s*([A-Z0-9][A-Z0-9\-_]{2,25})\b",
        text,
        re.IGNORECASE
    )
    if labeled_match:
        candidate = labeled_match.group(1).strip()
        # Hard reject: too long, contains spaces/commas, looks like a sentence
        if (len(candidate) <= 30
                and "," not in candidate
                and len(candidate.split()) == 1):
            return candidate.upper()

    return None


# ===============================
# FIX 6: TOTAL AMOUNT EXTRACTION
# Handles actual document formats:
#   | Total Amount | USD 950,000.00 |    (PR details table)
#   | TOTAL CONTRACT VALUE (USD) | $950,000.00 |    (line items table)
#   | Total PR Value | USD 950,000.00 |  (budget table)
# ===============================
def extract_total_amount(text):

    # Strategy 1: PR details / budget table cell
    # | Total Amount | USD 950,000.00 | or | Total PR Value | USD 950,000.00 |
    table_total_match = re.search(
        r"\|\s*\*{0,2}\s*(?:Total\s*(?:Amount|PR\s*Value|Value)|Grand\s*Total|PR\s*Value|Estimated\s*Value)"
        r"\s*\*{0,2}\s*\|\s*\*{0,2}\s*"
        r"([A-Z]{0,3}\s*[₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)"
        r"\s*\*{0,2}\s*\|",
        text,
        re.IGNORECASE
    )
    if table_total_match:
        return clean_value("total_amount", table_total_match.group(1))

    # Strategy 2: TOTAL CONTRACT VALUE row (bottom of line items table)
    # | TOTAL CONTRACT VALUE (USD) | $950,000.00 |
    contract_total_match = re.search(
        r"\|\s*\*{0,2}\s*TOTAL\s+CONTRACT\s+VALUE[^|]*\|\s*\*{0,2}\s*"
        r"([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)"
        r"\s*\*{0,2}\s*\|",
        text,
        re.IGNORECASE
    )
    if contract_total_match:
        return clean_value("total_amount", contract_total_match.group(1))

    # Strategy 3: Inline labeled (non-table)
    inline_match = re.search(
        r"(?:total\s*amount|grand\s*total|total\s*(?:pr\s*)?value|estimated\s*value)\s*[:\-]\s*"
        r"([A-Z]{0,3}\s*[₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)",
        text,
        re.IGNORECASE
    )
    if inline_match:
        return clean_value("total_amount", inline_match.group(1))

    # Strategy 4: Largest numeric value in any table pipe column
    table_amounts = re.findall(
        r"\|\s*([₹$€£]?\s*[\d,]{4,}(?:\.\d{1,2})?)\s*\|",
        text
    )
    if table_amounts:
        parsed = []
        for a in table_amounts:
            cleaned = re.sub(r"[₹$€£,\s]", "", a)
            try:
                parsed.append((float(cleaned), a.strip()))
            except ValueError:
                continue
        if parsed:
            largest = max(parsed, key=lambda x: x[0])
            return clean_value("total_amount", largest[1])

    # Strategy 5: Currency symbol directly preceding a number
    currency_match = re.search(r"[₹$€£]\s*([\d,]+(?:\.\d{1,2})?)", text)
    if currency_match:
        return clean_value("total_amount", currency_match.group(1))

    return None


# ===============================
# UNSTRUCTURED EXTRACTION
# ===============================
def extract_unstructured_sections(text):
    result = {}

    for field, aliases in UNSTRUCTURED_ALIASES.items():

        if field == "quantity":
            result[field] = extract_quantity(text)
            continue

        value = None

        for alias in aliases:
            section = extract_section(text, alias)
            if section:
                value = clean_value(field, section[:1000])
                break

        result[field] = value

    return result


# ===============================
# MAIN FUNCTION
# ===============================
def extract_with_rules(text):
    lines = text.split("\n")
    data = {}

    # Request Date
    data["request_date"] = extract_date(text)

    # Currency
    data["currency"] = extract_currency(text)

    # Requested By / Title
    name, title = extract_requested_by(text)
    data["requested_by"] = name
    data["requestor_title"] = title

    # Required Date
    data["required_date"] = extract_required_date(text)

    # PR ID
    # Must start with "PR-" to avoid matching "enterprise", "price", etc.
    pr_match = re.search(r"\bPR-[A-Z0-9][A-Z0-9\-\/]{2,}\b", text, re.IGNORECASE)
    if pr_match:
        data["pr_id"] = clean_value("pr_id", pr_match.group(0))

    # SOW Number
    sow_match = re.search(r"(SOW[-A-Z0-9\/]+)", text, re.IGNORECASE)
    if sow_match:
        data["reference_sow_number"] = clean_value("reference_sow_number", sow_match.group(1))

    # MSA Number
    msa_match = re.search(r"(MSA[-A-Z0-9\/]+)", text, re.IGNORECASE)
    if msa_match:
        data["reference_msa_number"] = clean_value("reference_msa_number", msa_match.group(1))

    # FIX 5: Service Code — strict table-cell extraction
    data["service_code"] = extract_service_code(text)

    # FIX 6: Total Amount — multi-strategy handles table cell formats
    data["total_amount"] = extract_total_amount(text)

    # Priority
    priority_match = re.search(
        r"(?:Priority|Urgency)\s*[:\-]?\s*(High|Medium|Low)",
        text,
        re.IGNORECASE
    )
    if priority_match:
        data["priority"] = priority_match.group(1).capitalize()

    # Approval Status
    status_match = re.search(
        r"(?:Approval Status|Status|PR Status)\s*[:\-]?\s*(Pending|Approved|Rejected)",
        text,
        re.IGNORECASE
    )
    if status_match:
        data["approval_status"] = status_match.group(1).capitalize()
    else:
        data["approval_status"] = "Pending"

    # Description
    description = extract_section(text, "description")
    data["description"] = (
        clean_value("description", description[:1000])
        if description else None
    )

    # Unstructured (quantity, location, description)
    unstructured_data = extract_unstructured_sections(text)
    data.update(unstructured_data)

    # Generic structured extraction for remaining fields
    for field, aliases in FIELD_ALIASES.items():

        # Skip already extracted
        if field in [
            "request_date",
            "required_date",
            "currency",
            "pr_id",
            "requested_by",
            "reference_sow_number",
            "reference_msa_number",
            "total_amount",
            "priority",
            "approval_status",
            "service_code"
        ]:
            continue

        value = None

        for i, line in enumerate(lines):
            norm_line = normalize(line)

            for alias in aliases:

                # Inline match
                if alias in norm_line:
                    raw_match = re.search(
                        rf"{re.escape(alias)}[:\-]?\s*(.+)",
                        line,
                        re.IGNORECASE
                    )
                    if raw_match:
                        candidate = raw_match.group(1).strip()
                        candidate = clean_value(field, candidate)
                        if is_valid_value(field, candidate):
                            value = candidate
                            break

                # Next-line match
                if alias in norm_line:
                    for j in range(i + 1, min(i + 4, len(lines))):
                        candidate = lines[j].strip()
                        candidate = clean_value(field, candidate)
                        if is_valid_value(field, candidate):
                            value = candidate
                            break

                if value:
                    break

            if value:
                break

        data[field] = value

    return data