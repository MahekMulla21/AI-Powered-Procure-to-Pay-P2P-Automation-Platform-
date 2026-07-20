import re

# ===============================
# STRUCTURED FIELD ALIASES
# ===============================
FIELD_ALIASES = {
    "vendor_name": [
        "vendor name", "vendor_name", "vendor-name",
        "service provider", "provider", "vendor"
    ],
    "vendor_id": [
        "vendor id", "gstin", "tax id", "registration number"
    ],
    "start_date": [
        "start date", "effective date", "agreement date", "commencement date"
    ],
    "end_date": [
        "end date", "termination date", "expiry date"
    ],
    "payment_terms": [
        "payment terms", "billing terms", "invoice terms"
    ],
    "currency": [
        "currency", "usd", "inr", "eur"
    ],
    "status": [
        "status"
    ],
    "msa_id": [
        "msa id", "agreement id", "contract id"
    ]
}

# ===============================
# UNSTRUCTURED FIELD ALIASES
# ===============================
UNSTRUCTURED_ALIASES = {
    "intellectual_property": [
        "intellectual property",
        "ip rights",
        "ownership",
        "work product"
    ],
    "dispute_resolution": [
        "dispute resolution",
        "arbitration",
        "mediation",
        "conflict resolution"
    ],
    "confidentiality": [
        "confidentiality",
        "non disclosure",
        "nda",
        "confidential information"
    ],
    "liability_clause": [
        "liability",
        "limitation of liability",
        "liability cap",
        "maximum liability"
    ],
    "indemnification_clause": [
        "indemnification",
        "indemnity",
        "hold harmless",
        "vendor responsibility"
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
    match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
        text
    )
    return match.group(0) if match else None

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

    if len(value) < 3:
        return False

    if value.lower() in ["or", "and", "the"]:
        return False

    if field == "vendor_id":
        return bool(re.search(r"[a-z0-9\-]{6,}", value.lower()))

    if field == "currency":
        return value.upper() in ["USD", "INR", "EUR"]

    if field == "vendor_name":
        return len(value.split()) >= 2

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
                value = section[:500]  # limit size
                break

        result[field] = value

    return result

# ===============================
# MAIN FUNCTION
# ===============================
def extract_with_rules(text):
    lines = text.split("\n")
    data = {}

    # ===============================
    # SPECIAL EXTRACTIONS
    # ===============================

    # Start Date
    data["start_date"] = extract_date(text)

    # Currency
    currency_match = re.search(r"\b(USD|INR|EUR)\b", text)
    data["currency"] = currency_match.group(1) if currency_match else None

    # Created By
    created_match = re.search(r"Created By\s*(.+)", text, re.IGNORECASE)
    data["created_by"] = created_match.group(1).strip() if created_match else None

    # Termination Clause
    termination = extract_section(text, "termination")
    data["termination_clause"] = termination[:400] if termination else None

    # ===============================
    # UNSTRUCTURED DATA
    # ===============================
    unstructured_data = extract_unstructured_sections(text)
    data.update(unstructured_data)

    # ===============================
    # GENERIC STRUCTURED EXTRACTION
    # ===============================
    for field, aliases in FIELD_ALIASES.items():

        # Skip already handled fields
        if field in ["start_date", "currency"]:
            continue

        value = None

        for i, line in enumerate(lines):
            norm_line = normalize(line)

            for alias in aliases:

                # Inline match
                match = re.search(rf"{alias}[:\-]?\s*(.+)", norm_line)
                if match:
                    candidate = match.group(1).strip()
                    if is_valid_value(field, candidate):
                        value = candidate
                        break

                # Next-line match
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