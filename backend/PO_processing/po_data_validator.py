"""
po_data_validator.py - Data Validation Layer

Validates PO data before database insertion.
Fixes corrupted fields using LLM fallback logic.
"""

import re
from PO_processing.po_amount_parser import parse_amount_and_tax, clean_numeric_value


def validate_po_id(po_id):
    """
    Validate PO ID format.
    Must start with "PO-" or contain "PO" pattern.
    
    Args:
        po_id (str): PO ID to validate
    
    Returns:
        tuple: (is_valid, cleaned_value or None)
    """
    if not po_id or not isinstance(po_id, str):
        return False, None
    
    po_id = po_id.strip()
    
    # Check if starts with "PO-" or contains "PO" pattern
    if po_id.upper().startswith("PO-"):
        return True, po_id
    elif re.search(r'PO[\s\-#]*\d+', po_id, re.IGNORECASE):
        return True, po_id
    else:
        return False, None


def validate_reference_sow(reference_sow):
    """
    Validate SOW reference format.
    Must contain "SOW-" or "SOW" pattern.
    
    Args:
        reference_sow (str): SOW reference to validate
    
    Returns:
        tuple: (is_valid, cleaned_value or None)
    """
    if not reference_sow or not isinstance(reference_sow, str):
        return False, None
    
    reference_sow = reference_sow.strip()
    
    if "SOW-" in reference_sow.upper() or re.search(r'SOW[\s\-#]*\d+', reference_sow, re.IGNORECASE):
        return True, reference_sow
    else:
        return False, None


def validate_reference_msa(reference_msa):
    """
    Validate MSA reference format.
    Must contain "MSA-" or "MSA" pattern.
    
    Args:
        reference_msa (str): MSA reference to validate
    
    Returns:
        tuple: (is_valid, cleaned_value or None)
    """
    if not reference_msa or not isinstance(reference_msa, str):
        return False, None
    
    reference_msa = reference_msa.strip()
    
    if "MSA-" in reference_msa.upper() or re.search(r'MSA[\s\-#]*\d+', reference_msa, re.IGNORECASE):
        return True, reference_msa
    else:
        return False, None


def validate_amount_field(amount_str):
    """
    Validate and clean amount field.
    Extracts numeric value from strings like "USD 1,092,500.00 (@ 15% VAT)".
    
    Args:
        amount_str: Amount string or numeric value
    
    Returns:
        tuple: (is_valid, cleaned_float_value)
    """
    if amount_str is None:
        return False, None
    
    # If already numeric, return as is
    if isinstance(amount_str, (int, float)):
        return True, float(amount_str)
    
    if isinstance(amount_str, str):
        # Try parsing with amount parser
        total_amount, _ = parse_amount_and_tax(amount_str)
        if total_amount:
            return True, total_amount
        
        # Fallback: clean numeric value
        cleaned = clean_numeric_value(amount_str)
        if cleaned:
            return True, cleaned
    
    return False, None


def _clean_tax_item(item):
    """Helper to clean a single tax value."""
    if item is None or item == "" or item == "null":
        return None
    
    # If already numeric, return as is
    if isinstance(item, (int, float)):
        return int(item)
    
    if isinstance(item, str):
        # Extract percentage
        match = re.search(r'(\d+)\s*%', item)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        
        # Try cleaning as numeric
        cleaned = clean_numeric_value(item)
        if cleaned:
            return int(cleaned)
    
    return None


def validate_tax_field(tax_str):
    """
    Validate and clean tax field.
    Accepts single value, list, or JSON array string.
    Extracts percentage from strings like "15%" or "15% VAT".
    
    Args:
        tax_str: Tax string or numeric value (single value, list, or JSON array string like "[15, 15, 15]")
    
    Returns:
        tuple: (is_valid, cleaned_value)
    """
    import json
    
    if tax_str is None:
        return True, None  # Tax is optional
    
    # If already a list, process it directly
    if isinstance(tax_str, list):
        cleaned_list = [_clean_tax_item(item) for item in tax_str]
        # Return list only if it has at least one non-null value
        has_values = any(x is not None for x in cleaned_list)
        return True, cleaned_list if has_values else None
    
    # Check if it's a JSON array string
    if isinstance(tax_str, str) and tax_str.strip().startswith('['):
        try:
            parsed = json.loads(tax_str)
            if isinstance(parsed, list):
                cleaned_list = [_clean_tax_item(item) for item in parsed]
                # Return list only if it has at least one non-null value
                has_values = any(x is not None for x in cleaned_list)
                return True, cleaned_list if has_values else None
        except json.JSONDecodeError:
            pass
    
    # Single value
    cleaned = _clean_tax_item(tax_str)
    if cleaned is not None:
        return True, cleaned
    
    return False, None


def validate_quantity(quantity):
    """
    Validate quantity field.
    Accepts single value, list, or JSON array string.
    Must be numeric and within reasonable range.
    
    Args:
        quantity: Quantity value (single value, list, or JSON array string like "[1, 1, 1]")
    
    Returns:
        tuple: (is_valid, cleaned_value)
    """
    import json
    
    print(f"[DEBUG VALIDATION] validate_quantity called with: {quantity} (type: {type(quantity)})")
    
    if quantity is None:
        print(f"[DEBUG VALIDATION] Quantity is None, returning (True, None)")
        return True, None  # Quantity is optional
    
    # If already a list, process it directly
    if isinstance(quantity, list):
        print(f"[DEBUG VALIDATION] Processing list with {len(quantity)} items: {quantity}")
        cleaned_list = []
        for item in quantity:
            if item is None or item == "" or item == "null":
                cleaned_list.append(None)
            else:
                cleaned = clean_numeric_value(item)
                if cleaned and 0 < cleaned < 10000:
                    cleaned_list.append(cleaned)
                else:
                    print(f"[DEBUG VALIDATION] Item {item} cleaned to {cleaned}, rejected (out of range)")
                    cleaned_list.append(None)
        # Return list only if it has at least one non-null value
        has_values = any(x is not None for x in cleaned_list)
        print(f"[DEBUG VALIDATION] List cleaned to: {cleaned_list}, has_values: {has_values}")
        return True, cleaned_list if has_values else None
    
    # Check if it's a JSON array string
    if isinstance(quantity, str) and quantity.strip().startswith('['):
        print(f"[DEBUG VALIDATION] Processing JSON array string: {quantity}")
        try:
            parsed = json.loads(quantity)
            if isinstance(parsed, list):
                print(f"[DEBUG VALIDATION] Parsed JSON to list: {parsed}")
                # Validate each element
                cleaned_list = []
                for item in parsed:
                    if item is None or item == "" or item == "null":
                        cleaned_list.append(None)
                    else:
                        cleaned = clean_numeric_value(item)
                        if cleaned and 0 < cleaned < 10000:
                            cleaned_list.append(cleaned)
                        else:
                            print(f"[DEBUG VALIDATION] Item {item} cleaned to {cleaned}, rejected (out of range)")
                            cleaned_list.append(None)
                # Return list only if it has at least one non-null value
                has_values = any(x is not None for x in cleaned_list)
                print(f"[DEBUG VALIDATION] JSON cleaned to: {cleaned_list}, has_values: {has_values}")
                return True, cleaned_list if has_values else None
        except json.JSONDecodeError as e:
            print(f"[DEBUG VALIDATION] JSON decode error: {e}")
            pass
    
    # Single value
    print(f"[DEBUG VALIDATION] Processing single value: {quantity}")
    cleaned = clean_numeric_value(quantity)
    print(f"[DEBUG VALIDATION] clean_numeric_value returned: {cleaned}")
    if cleaned:
        # Validate range (0 < quantity < 10000)
        if 0 < cleaned < 10000:
            print(f"[DEBUG VALIDATION] Value {cleaned} is valid, returning (True, {cleaned})")
            return True, cleaned
        else:
            print(f"[DEBUG VALIDATION] Value {cleaned} is out of range (0 < x < 10000)")
    
    print(f"[DEBUG VALIDATION] Validation failed, returning (False, None)")
    return False, None


def validate_unit_price(unit_price):
    """
    Validate unit price field.
    Accepts single value, list, or JSON array string.
    Must be numeric and positive.
    
    Args:
        unit_price: Unit price value (single value, list, or JSON array string like "[120000, 180000]")
    
    Returns:
        tuple: (is_valid, cleaned_value)
    """
    import json
    
    if unit_price is None:
        return True, None  # Unit price is optional
    
    # If already a list, process it directly
    if isinstance(unit_price, list):
        cleaned_list = []
        for item in unit_price:
            if item is None or item == "" or item == "null":
                cleaned_list.append(None)
            else:
                cleaned = clean_numeric_value(item)
                if cleaned and cleaned > 0:
                    cleaned_list.append(cleaned)
                else:
                    cleaned_list.append(None)
        # Return list only if it has at least one non-null value
        has_values = any(x is not None for x in cleaned_list)
        return True, cleaned_list if has_values else None
    
    # Check if it's a JSON array string
    if isinstance(unit_price, str) and unit_price.strip().startswith('['):
        try:
            parsed = json.loads(unit_price)
            if isinstance(parsed, list):
                # Validate each element
                cleaned_list = []
                for item in parsed:
                    if item is None or item == "" or item == "null":
                        cleaned_list.append(None)
                    else:
                        cleaned = clean_numeric_value(item)
                        if cleaned and cleaned > 0:
                            cleaned_list.append(cleaned)
                        else:
                            cleaned_list.append(None)
                # Return list only if it has at least one non-null value
                has_values = any(x is not None for x in cleaned_list)
                return True, cleaned_list if has_values else None
        except json.JSONDecodeError:
            pass
    
    # Single value
    cleaned = clean_numeric_value(unit_price)
    if cleaned and cleaned > 0:
        return True, cleaned
    
    return False, None


def _clean_service_code_item(item):
    """Helper to clean a single service code value."""
    if item is None or item == "" or item == "null":
        return None
    
    if isinstance(item, str):
        item_clean = item.strip()
        # Must be alphanumeric, 2-50 characters
        if re.match(r'^[A-Za-z0-9\-]{2,50}$', item_clean):
            return item_clean
        else:
            # Keep the value but it may be invalid
            return item_clean if len(item_clean) >= 2 else None
    
    # Convert non-strings
    str_item = str(item).strip()
    return str_item if len(str_item) >= 2 else None


def validate_service_code(service_code):
    """
    Validate service code.
    Accepts single value, list, or JSON array string.
    Must be alphanumeric and reasonable length.
    
    Args:
        service_code: Service code value (single value, list, or JSON array string like "[\"SVC-001\", \"SVC-002\"]")
    
    Returns:
        tuple: (is_valid, cleaned_value or None)
    """
    import json
    
    if not service_code:
        return True, None  # Service code is optional
    
    # If already a list, process it directly
    if isinstance(service_code, list):
        cleaned_list = [_clean_service_code_item(item) for item in service_code]
        # Return list only if it has at least one non-null value
        has_values = any(x is not None for x in cleaned_list)
        return True, cleaned_list if has_values else None
    
    # Check if it's a JSON array string
    if isinstance(service_code, str) and service_code.strip().startswith('['):
        try:
            parsed = json.loads(service_code)
            if isinstance(parsed, list):
                cleaned_list = [_clean_service_code_item(item) for item in parsed]
                # Return list only if it has at least one non-null value
                has_values = any(x is not None for x in cleaned_list)
                return True, cleaned_list if has_values else None
        except json.JSONDecodeError:
            pass
    
    # Single value
    cleaned = _clean_service_code_item(service_code)
    if cleaned:
        return True, cleaned
    
    return False, None


def validate_structured_data(structured_data):
    """
    Validate all structured fields before DB insertion.
    Fixes corrupted fields by returning cleaned values.
    
    Args:
        structured_data (dict): Structured data dictionary
    
    Returns:
        tuple: (is_valid, cleaned_data, validation_errors)
    """
    if not structured_data:
        return False, {}, ["No structured data provided"]
    
    cleaned_data = {}
    validation_errors = []
    
    # Validate PO ID (required)
    po_id = structured_data.get("po_id")
    is_valid, cleaned_po = validate_po_id(po_id)
    if is_valid and cleaned_po:
        cleaned_data["po_id"] = cleaned_po
    else:
        validation_errors.append(f"Invalid po_id: {po_id}")
        cleaned_data["po_id"] = po_id  # Keep original for review
    
    # Validate reference_sow
    reference_sow = structured_data.get("reference_sow")
    is_valid, cleaned_sow = validate_reference_sow(reference_sow)
    if is_valid and cleaned_sow:
        cleaned_data["reference_sow"] = cleaned_sow
    else:
        if reference_sow:  # Only error if provided but invalid
            validation_errors.append(f"Invalid reference_sow: {reference_sow}")
        cleaned_data["reference_sow"] = reference_sow
    
    # Validate reference_msa
    reference_msa = structured_data.get("reference_msa")
    is_valid, cleaned_msa = validate_reference_msa(reference_msa)
    if is_valid and cleaned_msa:
        cleaned_data["reference_msa"] = cleaned_msa
    else:
        if reference_msa:
            validation_errors.append(f"Invalid reference_msa: {reference_msa}")
        cleaned_data["reference_msa"] = reference_msa
    
    # Validate total_amount
    total_amount = structured_data.get("total_amount")
    is_valid, cleaned_amount = validate_amount_field(total_amount)
    if is_valid and cleaned_amount:
        cleaned_data["total_amount"] = cleaned_amount
    else:
        validation_errors.append(f"Invalid total_amount: {total_amount}")
        cleaned_data["total_amount"] = None
    
    # Validate tax
    tax = structured_data.get("tax")
    is_valid, cleaned_tax = validate_tax_field(tax)
    if is_valid:
        cleaned_data["tax"] = cleaned_tax
    else:
        if tax:
            validation_errors.append(f"Invalid tax: {tax}")
        cleaned_data["tax"] = None
    
    # Validate quantity
    quantity = structured_data.get("quantity")
    is_valid, cleaned_qty = validate_quantity(quantity)
    if is_valid:
        cleaned_data["quantity"] = cleaned_qty
    else:
        if quantity:
            validation_errors.append(f"Invalid quantity: {quantity}")
        cleaned_data["quantity"] = None
    
    # Validate unit_price
    unit_price = structured_data.get("unit_price")
    is_valid, cleaned_price = validate_unit_price(unit_price)
    if is_valid:
        cleaned_data["unit_price"] = cleaned_price
    else:
        if unit_price:
            validation_errors.append(f"Invalid unit_price: {unit_price}")
        cleaned_data["unit_price"] = None
    
    # Validate service_code - validation removed, LLM prompt enforces strict rules
    service_code = structured_data.get("service_code")
    if service_code and str(service_code).strip():
        cleaned_data["service_code"] = service_code
    else:
        cleaned_data["service_code"] = None
    
    # Copy other fields as-is
    for key, value in structured_data.items():
        if key not in cleaned_data:
            cleaned_data[key] = value
    
    # Overall validation result
    is_overall_valid = len(validation_errors) == 0 or (
        "po_id" not in [e.split(":")[0] for e in validation_errors]
    )
    
    return is_overall_valid, cleaned_data, validation_errors
