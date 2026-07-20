import re
from datetime import datetime


REQUIRED_FIELDS = [
    "po_id",
    "po_date",
    "vendor_name",
    "client_name",
    "payment_terms",
    "delivery_terms",
    "currency",
    "total_amount",
    "start_date",
    "end_date",
    "reference_sow",
    "reference_msa",
    "quantity",
    "unit_price",
    "tax",
    "tax_breakup",
    "service_code",
    "delivery_location",
    "grn_indicator",
    "po_status"
]


# ============================================================
# DATE NORMALIZER
# ============================================================

def normalize_date(date_value):
    """
    Convert dates to YYYY-MM-DD format.
    """

    if not date_value:
        return None

    if not isinstance(date_value, str):
        date_value = str(date_value)

    date_value = date_value.strip()

    # Already correct format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_value):
        return date_value

    formats = [

        "%B %d, %Y",   # February 01, 2024
        "%b %d, %Y",   # Feb 01, 2024
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%m/%d/%Y"
    ]

    for fmt in formats:

        try:

            parsed = datetime.strptime(date_value, fmt)

            return parsed.strftime("%Y-%m-%d")

        except Exception:
            continue

    return date_value


# ============================================================
# CLEAN NUMERIC VALUE
# ============================================================

def clean_numeric(value):

    if value is None:
        return None

    try:

        if isinstance(value, (int, float)):
            return float(value)

        value = str(value)

        cleaned = re.sub(r"[^\d.]", "", value)

        if not cleaned:
            return None

        return float(cleaned)

    except Exception:
        return None


# ============================================================
# CLEAN ARRAY FIELDS
# ============================================================

def clean_array_field(value):

    if value is None:
        return None

    if not isinstance(value, list):
        value = [value]

    cleaned = []

    for item in value:

        if item in [None, "", "null", "None"]:
            continue

        cleaned.append(item)

    return cleaned if cleaned else None


# ============================================================
# MAIN VALIDATOR
# ============================================================

def validate(data):
    """
    Validate PO data safely.
    """

    # ============================================================
    # EMPTY DATA
    # ============================================================

    if not data or not isinstance(data, dict):

        return {
            "structured": {},
            "unstructured": {}
        }

    structured = data.get("structured", {})

    if not structured or not isinstance(structured, dict):
        structured = {}

    # ============================================================
    # ENSURE ALL REQUIRED FIELDS
    # ============================================================

    for field in REQUIRED_FIELDS:

        if field not in structured:
            structured[field] = None

    # ============================================================
    # VALIDATE po_id
    # ============================================================

    po_id = structured.get("po_id")

    if not po_id or not str(po_id).strip():

        print("[WARN] po_id is missing or empty")

        structured["po_id"] = None

    else:

        structured["po_id"] = str(po_id).strip()

    # ============================================================
    # VALIDATE total_amount
    # ============================================================

    total_amount = structured.get("total_amount")

    cleaned_amount = clean_numeric(total_amount)

    if cleaned_amount is not None:

        structured["total_amount"] = cleaned_amount

    else:

        if total_amount:
            print(
                f"[WARN] total_amount "
                f"'{total_amount}' is invalid"
            )

        structured["total_amount"] = None

    # ============================================================
    # VALIDATE DATES
    # ============================================================

    date_fields = [
        "po_date",
        "start_date",
        "end_date"
    ]

    for field in date_fields:

        value = structured.get(field)

        if value:

            normalized = normalize_date(value)

            structured[field] = normalized

            if not re.match(
                r"^\d{4}-\d{2}-\d{2}$",
                str(normalized)
            ):

                print(
                    f"[WARN] {field} "
                    f"'{value}' could not be normalized"
                )

    # ============================================================
    # CLEAN ARRAY FIELDS
    # ============================================================

    array_fields = [
        "quantity",
        "unit_price",
        "tax",
        "service_code"
    ]

    for field in array_fields:

        structured[field] = clean_array_field(
            structured.get(field)
        )

    # ============================================================
    # CLEAN STRING FIELDS
    # ============================================================

    string_fields = [
        "vendor_name",
        "client_name",
        "payment_terms",
        "delivery_terms",
        "currency",
        "reference_sow",
        "reference_msa",
        "delivery_location",
        "grn_indicator",
        "po_status",
        "tax_breakup"
    ]

    for field in string_fields:

        value = structured.get(field)

        if value is not None:

            structured[field] = str(value).strip()

    # ============================================================
    # FINAL STRUCTURE
    # ============================================================

    data["structured"] = structured

    if "unstructured" not in data:
        data["unstructured"] = {}

    if data["unstructured"] is None:
        data["unstructured"] = {}

    # ============================================================
    # SUCCESS
    # ============================================================

    return data