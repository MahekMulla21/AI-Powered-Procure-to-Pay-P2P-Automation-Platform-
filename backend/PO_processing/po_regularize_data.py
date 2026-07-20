import re
import json
from typing import List, Dict, Any

from PO_processing.po_tabular_converter import (
    extract_tabular_data_from_text,
    normalize_tabular_field,
    TABULAR_ARRAY_FIELDS
)


# ============================================================
# SERVICE CODE VALIDATION
# ============================================================

def _is_valid_service_code(code: str) -> bool:

    if not code or not isinstance(code, str):
        return False

    code = code.strip()

    if len(code) < 2:
        return False

    if not re.match(r'^[A-Za-z0-9\-]+$', code):
        return False

    return True


# ============================================================
# SERVICE CODE EXTRACTION
# ============================================================

def _extract_service_codes_from_text(text: str) -> List[str]:

    codes = []
    seen = set()

    patterns = [

        # SVC-DM-001
        r'\b([A-Z]{2,20}(?:-[A-Z0-9]+)+)\b',

        # SOW001
        r'\b([A-Z]{2,6}\d{3,})\b',

        # after keywords
        r'(?:service\s*code|item\s*code|sow|msa)[.:\s]+([A-Z0-9][\w\-]{2,})'
    ]

    for pattern in patterns:

        for match in re.finditer(pattern, text, re.IGNORECASE):

            code = match.group(1).strip()

            if (
                _is_valid_service_code(code)
                and code not in seen
            ):

                codes.append(code)
                seen.add(code)

    return codes


# ============================================================
# UNIT PRICE EXTRACTION
# ============================================================

def _extract_unit_prices_from_text(text: str) -> List[float]:

    prices = []
    seen_positions = set()

    patterns = [

        r'(?:unit\s*price|rate|price\s+per\s+unit)[.:\s]+\$?([\d,]+(?:\.\d{1,2})?)',

        r'\$([\d,]+(?:\.\d{1,2})?)\s*(?:per|/|\()',

        r'(?:amount|price)[.:\s]+\$?([\d,]{3,}(?:\.\d{1,2})?)',

        r'\b([\d,]{4,}\.\d{2})\b'
    ]

    for pattern in patterns:

        for match in re.finditer(pattern, text, re.IGNORECASE):

            pos = match.start()

            if pos in seen_positions:
                continue

            seen_positions.add(pos)

            raw = match.group(1).replace(',', '')

            try:

                value = float(raw)

                if value > 0:
                    prices.append(value)

            except Exception:
                continue

    return prices


# ============================================================
# QUANTITY EXTRACTION
# ============================================================

def _extract_quantities_from_text(text: str) -> List[float]:

    quantities = []
    seen_positions = set()

    patterns = [

        r'(?:qty|quantity)[.:\s]+(\d+(?:\.\d+)?)',

        r'(\d+(?:\.\d+)?)\s+(?:units?|nos?|pcs|pieces|LS|lot|months?)'
    ]

    for pattern in patterns:

        for match in re.finditer(pattern, text, re.IGNORECASE):

            pos = match.start()

            if pos in seen_positions:
                continue

            seen_positions.add(pos)

            try:

                value = float(match.group(1))

                if 0 < value < 10000:
                    quantities.append(value)

            except Exception:
                continue

    return quantities


# ============================================================
# NORMALIZE LIST
# ============================================================

def _normalize_list(values):

    if values is None:
        return None

    if not isinstance(values, list):
        return [values]

    cleaned = []

    for item in values:

        if item in [None, "", "null", "None"]:
            continue

        cleaned.append(item)

    return cleaned if cleaned else None


# ============================================================
# MAIN REGULARIZER
# ============================================================

def regularize_po_data(
    text: str,
    existing_data: Dict[str, Any]
) -> Dict[str, Any]:

    print("[REGULARIZE] Starting data regularization...")

    if not existing_data:
        existing_data = {}

    result = dict(existing_data)

    # ============================================================
    # TABULAR EXTRACTION
    # ============================================================

    try:

        tabular_qty = extract_tabular_data_from_text(
            text,
            "quantity"
        )

        tabular_unit_price = extract_tabular_data_from_text(
            text,
            "unit_price"
        )

        tabular_service_code = extract_tabular_data_from_text(
            text,
            "service_code"
        )

        tabular_tax = extract_tabular_data_from_text(
            text,
            "tax"
        )

    except Exception as e:

        print(f"[REGULARIZE] Tabular extraction failed: {e}")

        tabular_qty = []
        tabular_unit_price = []
        tabular_service_code = []
        tabular_tax = []

    # ============================================================
    # QUANTITY
    # ============================================================

    qty_candidates = []

    if isinstance(tabular_qty, list) and tabular_qty:
        qty_candidates = tabular_qty

    else:
        qty_candidates = _extract_quantities_from_text(text)

    existing_qty = existing_data.get("quantity")

    if isinstance(existing_qty, list):

        if len(existing_qty) > len(qty_candidates):
            qty_candidates = existing_qty

    elif isinstance(existing_qty, (int, float)):
        qty_candidates = [float(existing_qty)]

    result["quantity"] = _normalize_list(qty_candidates)

    # ============================================================
    # UNIT PRICE
    # ============================================================

    price_candidates = []

    if isinstance(tabular_unit_price, list) and tabular_unit_price:
        price_candidates = tabular_unit_price

    else:
        price_candidates = _extract_unit_prices_from_text(text)

    existing_price = existing_data.get("unit_price")

    if isinstance(existing_price, list):

        if len(existing_price) > len(price_candidates):
            price_candidates = existing_price

    elif isinstance(existing_price, (int, float)):
        price_candidates = [float(existing_price)]

    result["unit_price"] = _normalize_list(price_candidates)

    # ============================================================
    # SERVICE CODE
    # ============================================================

    code_candidates = []

    if isinstance(tabular_service_code, list) and tabular_service_code:
        code_candidates = tabular_service_code

    else:
        code_candidates = _extract_service_codes_from_text(text)

    existing_codes = existing_data.get("service_code")

    if isinstance(existing_codes, list):

        if len(existing_codes) > len(code_candidates):
            code_candidates = existing_codes

    elif isinstance(existing_codes, str):
        code_candidates = [existing_codes]

    result["service_code"] = _normalize_list(code_candidates)

    # ============================================================
    # TAX
    # ============================================================

    tax_candidates = []

    if isinstance(tabular_tax, list) and tabular_tax:
        tax_candidates = tabular_tax

    existing_tax = existing_data.get("tax")

    if isinstance(existing_tax, list):
        tax_candidates = existing_tax

    elif isinstance(existing_tax, (int, float)):
        tax_candidates = [float(existing_tax)]

    # Expand single tax across all line items
    if (
        tax_candidates
        and len(tax_candidates) == 1
    ):

        qty_count = len(result.get("quantity") or [])

        if qty_count > 1:

            tax_candidates = tax_candidates * qty_count

            print(
                f"[REGULARIZE] Expanded tax "
                f"to {qty_count} items"
            )

    result["tax"] = _normalize_list(tax_candidates)

    # ============================================================
    # NORMALIZE TABULAR FIELDS
    # ============================================================

    for field in TABULAR_ARRAY_FIELDS:

        if field not in result:
            continue

        try:

            normalized = normalize_tabular_field(
                result[field],
                field
            )

            if normalized is not None:
                result[field] = normalized

        except Exception as e:

            print(
                f"[REGULARIZE] Failed to normalize "
                f"{field}: {e}"
            )

    # ============================================================
    # ENSURE LIST TYPES
    # ============================================================

    for field in [
        "quantity",
        "unit_price",
        "service_code",
        "tax"
    ]:

        if field not in result:
            continue

        value = result[field]

        if value is None:
            continue

        if not isinstance(value, list):
            result[field] = [value]

        if isinstance(result[field], list):

            if len(result[field]) == 0:
                result[field] = None

    print(f"[REGULARIZE] Final regularized data: {result}")

    return result


# ============================================================
# DATABASE RECORD FIXER
# ============================================================

def regularize_database_record(
    record: Dict[str, Any]
) -> Dict[str, Any]:

    result = dict(record)

    for field in TABULAR_ARRAY_FIELDS:

        if field not in result:
            continue

        value = result[field]

        if value is None:
            continue

        # Already proper list
        if isinstance(value, list):
            continue

        # Parse JSON array string
        if isinstance(value, str):

            value_str = value.strip()

            if (
                value_str.startswith('[')
                and value_str.endswith(']')
            ):

                try:

                    parsed = json.loads(value_str)

                    if isinstance(parsed, list):
                        result[field] = parsed
                        continue

                except Exception:
                    pass

        # Fallback normalize
        try:

            normalized = normalize_tabular_field(
                value,
                field
            )

            if normalized is not None:
                result[field] = normalized

        except Exception:
            pass

    return result