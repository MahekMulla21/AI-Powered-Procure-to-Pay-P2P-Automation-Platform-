"""
po_tabular_converter.py - Tabular Data to JSON Converter

Converts tabular fields (service_code, quantity, unit_price, tax) to JSON arrays
for database storage. ALWAYS returns arrays, even for single values.

Key fix: handles column-dump PDF layout where pdfminer extracts entire columns
sequentially rather than row-by-row.
"""

import json
import re
from typing import Union, List, Any

# Tabular fields that must ALWAYS be arrays
TABULAR_ARRAY_FIELDS = {"service_code", "quantity", "unit_price", "tax"}

# Header tokens to strip before parsing table data
_HEADER_TOKEN_SET = {
    '#', 'service', 'code', 'description', 'qty', 'quantity',
    'unit price', 'unit', 'price', '(usd)', 'usd', 'total (usd)',
    'total', 'milestone', 'amount', 'no', 'no.', 'sr', 'sr.',
    'item', 'particulars', 'rate', 'taxes', 'tax', 'vat', 'gst'
}

# Unit tokens that follow a quantity number
_UNIT_RE = re.compile(
    r'^(LS|lot|lots|units?|nos?|pcs|pieces|hours?|hr|days?|months?|'
    r'MD|man.?days?|FTE|month|lumpsum|lump\s*sum)$',
    re.IGNORECASE
)

# Table section start/end markers
_TABLE_START_KW = [
    'LINE ITEMS', 'DESCRIPTION OF GOODS', 'SERVICE ITEMS',
    'ITEMS & PRICES', 'ITEM DETAILS', 'SCHEDULE OF SERVICES',
    'SCOPE OF WORK', 'DELIVERABLES'
]
_TABLE_END_KW = [
    'SUBTOTAL', 'TAX BREAKUP', 'DELIVERY TERMS', 'PAYMENT TERMS',
    'TERMS AND CONDITIONS', 'NOTES', 'BANK DETAILS', 'AUTHORIZED'
]


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _is_header_token(t: str) -> bool:
    """Return True if token is a table header word to be skipped."""
    tl = t.lower().strip()
    return tl in _HEADER_TOKEN_SET or tl.startswith('(usd') or tl.startswith('(inr')


def _find_table_section(text: str) -> str:
    """
    Locate and return only the line-items table block from the full document text.
    Falls back to full text if no markers found.
    """
    start = -1
    for kw in _TABLE_START_KW:
        idx = text.upper().find(kw)
        if idx != -1:
            start = idx
            break
    if start == -1:
        return text

    end = len(text)
    for kw in _TABLE_END_KW:
        idx = text.upper().find(kw, start + 50)
        if idx != -1:
            end = min(end, idx)

    return text[start:end]


def _extract_line_items_column_dump(text: str) -> dict:
    """
    Core extractor for the column-dump PDF layout that pdfminer produces
    from multi-column tables. In this layout all row-1 cells appear first,
    then all row-2 cells, etc. — but actually pdfminer dumps ENTIRE COLUMNS
    sequentially:
        [row_numbers] [service_codes] [descriptions] [qty+unit] [unit_price] [total]

    Token indices from real PDF (verified against both sample documents):
      0-N  : intro paragraph tokens
      N+   : consecutive row numbers (1, 2, 3 ...)
      next : service code pairs ("SVC-DM-" + "001")
      next : description phrases
      next : quantity + unit token pairs ("2", "LS")
      next : unit_price and total price tokens (interleaved pairs)
    """
    print(f"[DEBUG COLUMN-DUMP] Starting column-dump extraction")

    table_text = _find_table_section(text)
    raw_tokens = [t.strip() for t in re.split(r'\n+', table_text) if t.strip()]
    print(f"[DEBUG COLUMN-DUMP] Raw tokens count: {len(raw_tokens)}")
    print(f"[DEBUG COLUMN-DUMP] First 30 raw tokens: {raw_tokens[:30]}")

    # Strip header words
    tokens = [t for t in raw_tokens if not _is_header_token(t)]
    print(f"[DEBUG COLUMN-DUMP] Tokens after header stripping: {len(tokens)}")
    print(f"[DEBUG COLUMN-DUMP] First 30 tokens: {tokens[:30]}")

    # ---- Find all row numbers scattered in the token list ----
    # In PDF column-dump layout, row numbers appear at the start of each row section
    # e.g., '1', then later '2', then '3', etc. - not consecutively
    row_numbers = []
    seen_numbers = set()

    for i, t in enumerate(tokens):
        if re.match(r'^\d+$', t):
            num = int(t)
            # Only collect if it's a reasonable row number (1-200) and not seen before
            if 1 <= num <= 200 and num not in seen_numbers:
                # Check if it's followed by service code pattern or description
                # This confirms it's a row number, not a quantity or year
                next_tokens = tokens[i+1:i+4] if i+1 < len(tokens) else []
                is_row_start = False

                # Pattern 1: Followed by service code prefix like "SVC-DM-"
                for nt in next_tokens:
                    if re.match(r'^[A-Z]{2,8}-', nt):
                        is_row_start = True
                        break
                    # Pattern 2: Followed by description text (contains lowercase)
                    if re.search(r'[a-z]{3,}', nt):
                        is_row_start = True
                        break

                if is_row_start or num == 1:  # Always accept "1" as first row
                    row_numbers.append(num)
                    seen_numbers.add(num)

    # Sort to ensure correct order
    row_numbers.sort()
    print(f"[DEBUG COLUMN-DUMP] Found row numbers: {row_numbers}")

    # Find first row number position to start extraction
    idx = 0
    while idx < len(tokens):
        if tokens[idx] == '1':
            break
        idx += 1

    n = len(row_numbers)
    if n == 0:
        print(f"[DEBUG COLUMN-DUMP] No row numbers found")
        return {}

    # ---- Service codes ----
    # Format 1 (split): "SVC-DM-" then "001" on next token
    # Format 2 (whole): "SVC-DM-001" on one token
    # Format 3: "POSTCIT-20240047" style codes
    service_codes = []
    temp_prefix = ''
    sc_start = idx
    print(f"[DEBUG COLUMN-DUMP] Starting service code extraction at idx {idx}, n={n}")
    print(f"[DEBUG COLUMN-DUMP] Tokens at service code position: {tokens[idx:idx+20]}")

    while idx < len(tokens) and len(service_codes) < n:
        t = tokens[idx]
        if temp_prefix:
            # previous token was a partial code ending with hyphen
            service_codes.append(temp_prefix + t)
            temp_prefix = ''
            idx += 1
            continue
        elif re.match(r'^[A-Z]{2,20}-[A-Z0-9]+-$', t):
            # ends with trailing hyphen = split across lines
            temp_prefix = t
            idx += 1
            continue
        elif re.match(r'^[A-Z]{2,20}(?:-[A-Z0-9]+)+$', t) and not t.isdigit():
            # complete code on one token e.g. "SVC-DM-001", "POSTCIT-20240047"
            service_codes.append(t)
            idx += 1
            continue
        elif re.match(r'^[A-Z]{2,6}\d{3,}$', t) and not t.isdigit():
            # Format like "SOW001", "SVC123"
            service_codes.append(t)
            idx += 1
            continue
        elif re.match(r'^\d{3,}$', t) and len(service_codes) > 0 and re.match(r'^[A-Z]+', tokens[sc_start] if sc_start < len(tokens) else ''):
            # Just a number that might be part of a code sequence
            # Check if previous service code had similar prefix
            prev_code = service_codes[-1] if service_codes else ''
            prefix_match = re.match(r'^([A-Z]+[-]?\d{3,})', prev_code)
            if prefix_match:
                # Try to construct similar code
                base = re.sub(r'\d+$', '', prev_code)
                service_codes.append(base + t)
                idx += 1
                continue
        else:
            # token is not a code — stop
            break

    if temp_prefix and service_codes:
        # orphaned prefix — unlikely but safe
        service_codes.append(temp_prefix.rstrip('-'))

    print(f"[DEBUG COLUMN-DUMP] Service codes found: {service_codes}")

    # If nothing matched, service codes may not be present in this doc
    if not service_codes:
        idx = sc_start  # reset so we don't skip real data
        print(f"[DEBUG COLUMN-DUMP] No service codes found, resetting idx to {sc_start}")

    # ---- Skip descriptions ----
    desc_count = 0
    while idx < len(tokens) and desc_count < n:
        t = tokens[idx]
        if (re.search(r'[a-zA-Z]{3,}', t)
                and not re.match(r'^\$', t)
                and not _UNIT_RE.match(t)
                and not re.match(r'^M\d\s*[–\-]', t)
                and not re.match(r'^[A-Z]{2,8}-[A-Z0-9]+-?', t)):
            desc_count += 1
        idx += 1

    # ---- Quantities ----
    qty_start_idx = idx
    quantities = []
    print(f"[DEBUG COLUMN-DUMP] Starting quantity extraction at idx {idx}, n={n}")
    print(f"[DEBUG COLUMN-DUMP] Tokens at qty position: {tokens[idx:idx+20]}")

    while idx < len(tokens) and len(quantities) < n:
        t = tokens[idx]
        if re.match(r'^\d+(?:\.\d+)?$', t):
            val = float(t)
            nxt = tokens[idx + 1] if idx + 1 < len(tokens) else ''
            if _UNIT_RE.match(nxt):
                quantities.append(val)
                print(f"[DEBUG COLUMN-DUMP] Qty with unit: {val} {nxt}")
                idx += 2  # consume number AND unit
                continue
            elif (re.match(r'^\$[\d,]', nxt)
                  or re.match(r'^[\d,]+\.\d{2}$', nxt)
                  or re.match(r'^M\d', nxt)):
                # Next is a price or milestone = bare quantity
                quantities.append(val)
                print(f"[DEBUG COLUMN-DUMP] Bare qty (before price): {val}")
                idx += 1
                continue
            else:
                # Bare quantity with no clear following token - accept it
                quantities.append(val)
                print(f"[DEBUG COLUMN-DUMP] Bare qty: {val}")
                idx += 1
                continue
        idx += 1

    print(f"[DEBUG COLUMN-DUMP] Final quantities: {quantities}")

    # ---- Unit prices ----
    # Column dump layout produces price tokens in this order:
    #   [up1, total1, up2, total2, ... upN, totalN]   (interleaved)
    # OR:
    #   [up1, up2, ... upN, total1, total2, ... totalN] (blocked)
    # Detect by checking if count == 2*n and use stride-2 for interleaved,
    # or take first n for blocked.
    all_prices = []
    price_tokens = tokens[idx:idx+50]  # Look at next 50 tokens for prices
    print(f"[DEBUG COLUMN-DUMP] Looking for prices in tokens: {price_tokens[:30]}")

    for t in tokens[idx:]:
        # Match $X,XXX.XX or $XXXX.XX format
        if re.match(r'^\$[\d,]+(?:\.\d{1,2})?$', t):
            val = float(t.replace('$', '').replace(',', ''))
            all_prices.append(val)
            print(f"[DEBUG COLUMN-DUMP] Price with $: {val}")
        # Match X,XXX.XX or XXXX.XX format
        elif re.match(r'^[\d,]+\.\d{2}$', t):
            val = float(t.replace(',', ''))
            if val > 100:  # Likely a price
                all_prices.append(val)
                print(f"[DEBUG COLUMN-DUMP] Price (decimal): {val}")
        # Match large numbers with 3+ digits
        elif re.match(r'^\d{4,}$', t):
            val = float(t)
            if val > 1000:  # Likely a price
                all_prices.append(val)
                print(f"[DEBUG COLUMN-DUMP] Price (large int): {val}")

    print(f"[DEBUG COLUMN-DUMP] All prices found: {all_prices}")

    unit_prices = None
    if len(all_prices) == 2 * n:
        # Stride-2: even indices = unit prices, odd indices = totals
        unit_prices = [all_prices[i * 2] for i in range(n)]
        print(f"[DEBUG COLUMN-DUMP] Unit prices (interleaved): {unit_prices}")
    elif len(all_prices) >= n:
        # Blocked: first n = unit prices
        unit_prices = all_prices[:n]
        print(f"[DEBUG COLUMN-DUMP] Unit prices (blocked): {unit_prices}")
    elif all_prices and len(all_prices) < n:
        # Partial match - use what we have
        unit_prices = all_prices
        print(f"[DEBUG COLUMN-DUMP] Unit prices (partial): {unit_prices}")
    else:
        print(f"[DEBUG COLUMN-DUMP] No unit prices found")

    result = {
        'service_code': service_codes if service_codes else None,
        'quantity':     quantities if quantities else None,
        'unit_price':   unit_prices,
    }
    print(f"[DEBUG COLUMN-DUMP] Final result: {result}")
    return result


def _extract_tax_from_text(text: str) -> Union[List, None]:
    """
    Extract tax values from document text.
    Priority: explicit uniform % rate > per-line % rates > absolute amounts.
    Returns ONLY the main tax rate (e.g., [15.0] for VAT @ 15%).
    """
    print(f"[DEBUG TAX] Starting tax extraction")

    # 1. Explicit uniform rate: "VAT @ 15%" / "GST @ 18%" / "TAX @ 15%"
    # Look for patterns like "KSA VAT @ 15%" or "VAT @ 15%"
    patterns = [
        r'(?:KSA\s+)?VAT\s*@\s*(\d+(?:\.\d+)?)\s*%',
        r'(?:KSA\s+)?GST\s*@\s*(\d+(?:\.\d+)?)\s*%',
        r'TAX\s*@\s*(\d+(?:\.\d+)?)\s*%',
        r'(?:vat|gst|tax)\s*rate.*?@\s*(\d+(?:\.\d+)?)\s*%',
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            rate = float(m.group(1))
            print(f"[DEBUG TAX] Found explicit rate: {rate}%")
            return [rate]

    # 2. Look in tax breakup section for the main rate (first occurrence)
    tax_section_match = re.search(
        r'(?:TAX BREAKUP|TAX DETAILS|VAT BREAKUP|GST BREAKUP|Tax Breakup).*?(?:\n\n|\Z)',
        text, re.IGNORECASE | re.DOTALL
    )

    if tax_section_match:
        search_area = tax_section_match.group(0)
        print(f"[DEBUG TAX] Found tax section: {search_area[:200]}")

        # Find first percentage in tax section (should be the main rate)
        m = re.search(r'@\s*(\d+(?:\.\d+)?)\s*%', search_area)
        if m:
            rate = float(m.group(1))
            print(f"[DEBUG TAX] Found rate in tax section: {rate}%")
            return [rate]

    # 3. Last resort: find any VAT/GST mention with percentage
    m = re.search(r'(?:VAT|GST|TAX).*?(\d+(?:\.\d+)?)\s*%', text, re.IGNORECASE)
    if m:
        rate = float(m.group(1))
        if 0 < rate <= 30:  # Reasonable tax rate range
            print(f"[DEBUG TAX] Found rate from general search: {rate}%")
            return [rate]

    print(f"[DEBUG TAX] No tax rate found")
    return None


def _extract_from_line_items_table(text: str) -> dict:
    """
    Smart extractor that finds the LINE ITEMS table and extracts
    service codes, quantities, and unit prices for each row.
    Returns dict with 'service_code', 'quantity', 'unit_price' as lists.
    """
    print(f"[DEBUG LINE-ITEMS] Starting smart table extraction")

    # Find the LINE ITEMS section
    line_items_match = re.search(
        r'LINE ITEMS.*?(?:SUBTOTAL|TAX BREAKUP|DELIVERY TERMS|PAYMENT TERMS)',
        text, re.IGNORECASE | re.DOTALL
    )
    if not line_items_match:
        print(f"[DEBUG LINE-ITEMS] No LINE ITEMS section found")
        return {}

    section = line_items_match.group(0)
    print(f"[DEBUG LINE-ITEMS] Found section: {section[:500]}")

    result = {
        'service_code': [],
        'quantity': [],
        'unit_price': [],
        'description': []  # Also capture descriptions
    }

    # Pattern to match each row: row_num, service_code_parts, description, qty, unit, price, total, milestone
    # Example: '1', 'SVC-DM-', '001', 'Discovery & Assessment', '1', 'LS', '$120,000.00', '$120,000.00', 'M1 – Mar 31,', '2024'
    row_pattern = r'''
        (\d+)\s*                                 # Row number
        (SVC-[A-Z]+-)\s*                         # Service code prefix
        (\d+)\s*                                 # Service code number
        ([^\d$]{5,50})\s*                       # Description (5-50 non-digit chars)
        (\d+(?:\.\d+)?)\s*                       # Quantity
        (LS|lot|units?)\s*                       # Unit
        \$([\d,]+(?:\.\d{2})?)\s*               # Unit Price
        \$[\d,]+(?:\.\d{2})?\s*                  # Total (skip)
        (M\d[^\n]*)                              # Milestone
    '''

    rows_found = 0
    for match in re.finditer(row_pattern, section, re.VERBOSE | re.IGNORECASE):
        row_num, svc_prefix, svc_num, desc, qty, unit, price = match.groups()[:7]

        # Build service code
        service_code = f"{svc_prefix}{svc_num}"

        # Clean price
        price_val = float(price.replace(',', ''))

        # Clean quantity
        qty_val = float(qty)

        result['service_code'].append(service_code)
        result['quantity'].append(qty_val)
        result['unit_price'].append(price_val)
        result['description'].append(desc.strip())  # Capture description
        rows_found += 1

        print(f"[DEBUG LINE-ITEMS] Row {row_num}: {service_code}, desc='{desc.strip()}', qty={qty_val}, price={price_val}")

    if rows_found > 0:
        print(f"[DEBUG LINE-ITEMS] Extracted {rows_found} rows successfully")
        return result

    # Fallback: Try simpler pattern without description
    print(f"[DEBUG LINE-ITEMS] Trying simpler pattern...")
    simple_pattern = r'(\d+)\s+(SVC-[A-Z]+-)\s*(\d+)\s+(\d+)\s+(LS)\s+\$([\d,]+(?:\.\d{2})?)'
    for match in re.finditer(simple_pattern, section, re.IGNORECASE):
        row_num, svc_prefix, svc_num, qty, unit, price = match.groups()

        service_code = f"{svc_prefix}{svc_num}"
        price_val = float(price.replace(',', ''))
        qty_val = float(qty)

        result['service_code'].append(service_code)
        result['quantity'].append(qty_val)
        result['unit_price'].append(price_val)
        rows_found += 1

    print(f"[DEBUG LINE-ITEMS] Simple pattern found {rows_found} rows")
    return result if rows_found > 0 else {}


def _fallback_regex_extract(text: str, field_name: str) -> Union[List, None]:
    """
    Regex fallback for when column-dump parser finds nothing.
    Used when document has a simple inline table (not multi-column PDF layout).
    Does NOT deduplicate numeric arrays — preserves all values including repeats.
    """
    print(f"[DEBUG FALLBACK] Starting extraction for '{field_name}'")

    patterns = {
        "quantity": [
            r'(?:qty|quantity|units?|nos?)[.:\s]+(\d+(?:\.\d+)?)',
            r'(\d{1,4}(?:\.\d+)?)\s+(?:units?|nos?|pcs|pieces|hours?|days?|months?|LS|lot|Lot|LOT)',
            r'(?:^|\s)(\d{1,3}(?:\.\d+)?)\s+(?:LS|lot|Lot|LOT)(?:\s|$|\n|\t)',
        ],
        "unit_price": [
            r'(?:unit\s*price|rate|price\s+per\s+unit|unit\s*rate|cost\s+per\s+unit)'
            r'[.:\s]+[\$₹€]?\s*([\d,]+(?:\.\d{1,2})?)',
            r'\$([\d,]+(?:\.\d{2})?)',
            r'(?:amount|price|total)[.:\s]+[\$₹€]?\s*([\d,]+(?:\.\d{2})?)',
        ],
        "tax": [
            r'(?:tax|gst|vat|igst|cgst|sgst)\s*@\s*(\d+(?:\.\d+)?)\s*%',
            r'(?:vat|gst)\s*@\s*(\d+(?:\.\d+)?)\s*%',
            r'(?:tax|vat|gst)\s*(\d+(?:\.\d+)?)\s*%',
        ],
        "service_code": [
            r'(?:service\s*code|item\s*code|sku)[.:\s]+([A-Z0-9][\w\-]{2,})',
            r'\b([A-Z]{3,8}-[A-Z]{2,4}-\d{3,4})\b',
            r'\b([A-Z]{3,8}-DM-\d{3})\b',
            r'\b([A-Z]{2,6}\d{3,})\b',
        ],
    }

    values = []
    all_matches = []  # Track all matches for debugging

    for pattern in patterns.get(field_name, []):
        print(f"[DEBUG FALLBACK] Pattern: {pattern[:60]}...")
        for m in re.finditer(pattern, text, re.IGNORECASE):
            raw = m.group(1)
            all_matches.append((m.group(0), raw, m.start()))
            if field_name in ("quantity", "unit_price", "tax"):
                try:
                    val = float(raw.replace(',', ''))
                    values.append(val)
                    print(f"[DEBUG FALLBACK] Match: '{m.group(0)}' -> {val}")
                except ValueError:
                    print(f"[DEBUG FALLBACK] Failed to parse: '{raw}'")
                    pass
            else:
                values.append(raw.strip())
                print(f"[DEBUG FALLBACK] Match: '{m.group(0)}' -> '{raw}'")

    print(f"[DEBUG FALLBACK] All matches: {all_matches}")
    print(f"[DEBUG FALLBACK] Final values for '{field_name}': {values}")
    return values if values else None


# ============================================================
# PUBLIC API — called by po_rule_based_extractor.py
# ============================================================

def extract_tabular_data_from_text(text: str, field_name: str) -> Union[List, None]:
    """
    Main entry point. Extracts tabular field arrays from document text.

    Handles the column-dump PDF layout produced by pdfminer from multi-column
    tables, where all values of one column appear together rather than row-by-row.

    Args:
        text:       Full document text (from PDF extraction or OCR)
        field_name: One of: service_code | quantity | unit_price | tax

    Returns:
        List of values, or None if not found.
        Numeric fields (quantity, unit_price, tax) return List[float].
        service_code returns List[str].
        Order matches the document's row order. Duplicates are preserved.
    """
    if not text or field_name not in TABULAR_ARRAY_FIELDS:
        return None

    print(f"[DEBUG TABULAR] Extracting '{field_name}' (text length: {len(text)})")

    if field_name == "tax":
        result = _extract_tax_from_text(text)
        print(f"[DEBUG TABULAR] tax result: {result}")
        return result

    # Try smart LINE ITEMS table extractor first
    line_items = _extract_from_line_items_table(text)
    if line_items and field_name in line_items and line_items[field_name]:
        print(f"[DEBUG TABULAR] LINE-ITEMS result for '{field_name}': {line_items[field_name]}")
        return line_items[field_name]

    # Fallback to column-dump parser
    line_items = _extract_line_items_column_dump(text)
    result = line_items.get(field_name)
    if result:
        print(f"[DEBUG TABULAR] column-dump result for '{field_name}': {result}")
        return result

    # Final fallback for simpler/inline table formats
    result = _fallback_regex_extract(text, field_name)
    print(f"[DEBUG TABULAR] fallback result for '{field_name}': {result}")
    return result


# ============================================================
# NORMALIZER — called by po_postgres_writer.py
# ============================================================

def _clean_numeric_value(value_str: str) -> Union[float, None]:
    """Strip currency symbols/commas and convert to float."""
    cleaned = re.sub(r'[^\d.]', '', str(value_str))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _is_valid_array_content(value: Any, field_name: str) -> bool:
    """Reject plain-text descriptions masquerading as array values."""
    if value is None:
        return False
    value_str = str(value).strip()

    # For numeric fields, reject year values (1900-2100) and other invalid numbers
    if field_name in ("quantity", "unit_price"):
        try:
            num = float(value_str.replace(',', ''))
            # Reject years
            if 1900 <= num <= 2100:
                return False
            # Reject negative and unreasonably large values for quantity
            if field_name == "quantity":
                if num < 0 or num > 10000:
                    return False
        except ValueError:
            pass

    # For service codes, require specific pattern
    if field_name == "service_code":
        # If it's a list, check each item individually
        if isinstance(value, list):
            for item in value:
                if item is None:
                    continue
                item_str = str(item).strip()
                # Must look like SVC-DM-001, POSTCIT-20240047, etc.
                if not re.match(r'^[A-Z]{2,}(?:-[A-Z0-9]+)+$', item_str):
                    return False
                # Reject codes that look like header/footer text
                invalid_codes = ['Description', 'Taxable', 'STC-IT-202', 'TCS-STC-202', 'STC-DM-202']
                if item_str in invalid_codes or any(item_str.startswith(ic) for ic in invalid_codes):
                    return False
            return True  # All items passed validation
        else:
            # Single value check
            if not re.match(r'^[A-Z]{2,}(?:-[A-Z0-9]+)+$', value_str):
                return False
            invalid_codes = ['Description', 'Taxable', 'STC-IT-202', 'TCS-STC-202', 'STC-DM-202']
            if value_str in invalid_codes or any(value_str.startswith(ic) for ic in invalid_codes):
                return False

    invalid_patterns = [
        r'quantity\s+unit\s+price',
        r'linked\s+project',
        r'description',
        r'please\s+find',
        r'see\s+attached',
        r'refer\s+to',
    ]
    for p in invalid_patterns:
        if re.search(p, value_str, re.IGNORECASE):
            return False
    return bool(re.search(r'[a-zA-Z0-9]', value_str))


def normalize_tabular_field(value: Any, field_name: str) -> Union[List, None]:
    """
    Normalize any value to a JSON array suitable for a JSONB column.

    Always returns a list (or None). Preserves order and duplicates.

    Examples:
        normalize_tabular_field("SVC-DM-001", "service_code")
        → ["SVC-DM-001"]

        normalize_tabular_field([2.0, 1.0, 5.0], "quantity")
        → [2.0, 1.0, 5.0]

        normalize_tabular_field('["120000.00","180000.00"]', "unit_price")
        → [120000.0, 180000.0]
    """
    if field_name not in TABULAR_ARRAY_FIELDS:
        return None
    if value is None:
        return None
    if not _is_valid_array_content(value, field_name):
        return None

    is_numeric = field_name in ("quantity", "unit_price", "tax")

    def _coerce(x):
        if x is None or (isinstance(x, str) and x.strip().lower() in ('', 'null')):
            return None
        if is_numeric:
            if isinstance(x, (int, float)):
                return float(x)
            return _clean_numeric_value(str(x))
        return str(x)

    # Already a list
    if isinstance(value, list):
        result = [_coerce(x) for x in value]
        return result if any(x is not None for x in result) else None

    value_str = str(value).strip()
    if value_str == '' or value_str.lower() == 'null':
        return None

    # JSON array string
    if value_str.startswith('[') and value_str.endswith(']'):
        try:
            parsed = json.loads(value_str)
            if isinstance(parsed, list):
                result = [_coerce(x) for x in parsed]
                return result if any(x is not None for x in result) else None
        except json.JSONDecodeError:
            pass

    # Comma-separated — but only if comma is NOT a thousands separator
    if ',' in value_str and not re.match(r'^[\$\s\d,\.]+$', value_str):
        parts = [p.strip() for p in value_str.split(',')]
        if len(parts) > 1:
            result = [_coerce(p) for p in parts]
            return result if any(x is not None for x in result) else None

    # Single value — wrap in list
    coerced = _coerce(value_str)
    return [coerced] if coerced is not None else None


def convert_to_jsonb(value: Any, field_name: str) -> str:
    """Convert value to JSONB-compatible JSON string for database storage."""
    normalized = normalize_tabular_field(value, field_name)
    if normalized is None:
        return "null"
    try:
        return json.dumps(normalized)
    except (TypeError, ValueError):
        return "null"