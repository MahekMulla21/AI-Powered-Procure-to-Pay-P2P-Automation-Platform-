"""
po_tax_breakup_normalizer.py - Tax Breakup Normalization Module

Normalizes tax_breakup field to ensure consistent JSONB storage.
Converts various input formats to structured JSON objects.
"""

import re
import json
from typing import Optional, Dict, Any, Union


def normalize_tax_breakup(tax_breakup: Union[str, Dict, None]) -> Optional[Dict[str, Any]]:
    """
    Normalize tax_breakup to valid JSON dict for JSONB storage.
    
    Args:
        tax_breakup: Input value (string, dict, or None)
    
    Returns:
        Dict with structured tax info OR None if invalid
    
    Examples:
        >>> normalize_tax_breakup("ksa vat 15")
        {'type': 'VAT', 'region': 'KSA', 'rate': 15}
        
        >>> normalize_tax_breakup({"type": "GST", "rate": 18})
        {'type': 'GST', 'rate': 18}
        
        >>> normalize_tax_breakup(None)
        None
    """
    # Handle None or empty
    if tax_breakup is None or str(tax_breakup).strip() == "":
        return None
    
    # If already a dict, validate and return
    if isinstance(tax_breakup, dict):
        # Ensure it's a valid dict (not empty)
        if tax_breakup:
            return tax_breakup
        return None
    
    # If string, try to parse as JSON first
    if isinstance(tax_breakup, str):
        tax_breakup = tax_breakup.strip()
        
        # Try to parse as JSON
        try:
            parsed = json.loads(tax_breakup)
            if isinstance(parsed, dict) and parsed:
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass  # Not valid JSON, continue with text parsing
        
        # Parse text format like "ksa vat 15" or "15% VAT"
        return _parse_tax_string(tax_breakup)
    
    # Invalid type
    return None


def _parse_tax_string(tax_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse tax string into structured JSON object.
    
    Supports formats:
    - "ksa vat 15" → {"type": "VAT", "region": "KSA", "rate": 15}
    - "15% VAT" → {"type": "VAT", "rate": 15}
    - "GST 18%" → {"type": "GST", "rate": 18}
    - "tax: 15%" → {"type": "TAX", "rate": 15}
    
    Args:
        tax_str: Tax description string
    
    Returns:
        Structured dict OR None if unparseable
    """
    if not tax_str:
        return None
    
    tax_str = tax_str.lower().strip()
    
    # Extract tax type (VAT, GST, TAX, etc.)
    tax_type = "TAX"  # Default
    if "vat" in tax_str:
        tax_type = "VAT"
    elif "gst" in tax_str:
        tax_type = "GST"
    elif "igst" in tax_str:
        tax_type = "IGST"
    elif "cgst" in tax_str:
        tax_type = "CGST"
    elif "sgst" in tax_str:
        tax_type = "SGST"
    
    # Extract region (KSA, USA, IND, etc.)
    region = None
    region_patterns = {
        "ksa": "KSA",
        "saudi": "KSA",
        "usa": "USA",
        "us": "USA",
        "ind": "IND",
        "india": "IND",
        "uk": "UK",
        "uae": "UAE",
        "eu": "EU",
        "europe": "EU"
    }
    
    for pattern, region_code in region_patterns.items():
        if pattern in tax_str:
            region = region_code
            break
    
    # Extract rate (percentage or numeric value)
    rate = None
    rate_match = re.search(r'(\d+(?:\.\d+)?)\s*%?', tax_str)
    if rate_match:
        try:
            rate = float(rate_match.group(1))
        except ValueError:
            pass
    
    # Build result dict
    result = {"type": tax_type}
    if region:
        result["region"] = region
    if rate is not None:
        result["rate"] = rate
    
    # Only return if we have meaningful data
    if len(result) > 1 or rate is not None:
        return result
    
    return None


def validate_tax_breakup(tax_breakup: Any) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Validate and normalize tax_breakup for database insertion.
    
    Args:
        tax_breakup: Input value to validate
    
    Returns:
        Tuple: (is_valid, normalized_value)
    
    Examples:
        >>> validate_tax_breakup("ksa vat 15")
        (True, {'type': 'VAT', 'region': 'KSA', 'rate': 15})
        
        >>> validate_tax_breakup(None)
        (True, None)
        
        >>> validate_tax_breakup("invalid")
        (True, None)  # Invalid input returns None but doesn't fail
    """
    normalized = normalize_tax_breakup(tax_breakup)
    
    # Normalized value is either a dict or None - both are valid
    return True, normalized


def ensure_jsonb_format(tax_breakup: Any) -> str:
    """
    Ensure tax_breakup is in JSONB-compatible string format.
    
    Args:
        tax_breakup: Input value
    
    Returns:
        JSON string suitable for JSONB column
    
    Examples:
        >>> ensure_jsonb_format("ksa vat 15")
        '{"type": "VAT", "region": "KSA", "rate": 15}'
        
        >>> ensure_jsonb_format(None)
        'null'
    """
    normalized = normalize_tax_breakup(tax_breakup)
    
    if normalized is None:
        return "null"
    
    try:
        return json.dumps(normalized)
    except (TypeError, ValueError):
        return "null"
