"""
po_amount_parser.py - Clean Amount Parsing Module

Extracts amount and tax from formatted strings like:
"USD 1,092,500.00 (@ 15% VAT)"
"Total: $5,000.00 including 10% tax"
"""

import re


def parse_amount_and_tax(amount_str):
    """
    Parse amount and tax from formatted amount strings.
    
    Args:
        amount_str (str): Amount string like "USD 1,092,500.00 (@ 15% VAT)"
    
    Returns:
        tuple: (total_amount as float, tax as int/None)
               Returns (None, None) if parsing fails
    """
    if not amount_str or not isinstance(amount_str, str):
        return None, None
    
    amount_str = amount_str.strip()
    
    # Extract numeric amount (handles: $1,234.56, USD 1,234.56, 1,234.56)
    amount_match = re.search(
        r'[\$€₹\w]*\s*([\d,]+(?:\.\d{1,2})?)',
        amount_str
    )
    
    if not amount_match:
        return None, None
    
    # Clean amount: remove commas, convert to float
    amount_cleaned = amount_match.group(1).replace(',', '')
    try:
        total_amount = float(amount_cleaned)
    except ValueError:
        return None, None
    
    # Extract tax percentage (handles: 15%, 15 %, @ 15% VAT, including 10% tax)
    tax_match = re.search(
        r'@?\s*(\d+)\s*%|(\d+)\s*%\s*(?:VAT|tax|GST)',
        amount_str,
        re.IGNORECASE
    )
    
    tax = None
    if tax_match:
        tax_value = tax_match.group(1) or tax_match.group(2)
        try:
            tax = int(tax_value)
        except ValueError:
            pass
    
    return total_amount, tax


def clean_numeric_value(value):
    """
    Clean numeric value by removing currency symbols, text, and commas.
    Returns float or None.
    
    Args:
        value: String or numeric value
    
    Returns:
        float or None
    """
    print(f"[DEBUG CLEAN] clean_numeric_value called with: {value} (type: {type(value)})")
    
    if value is None:
        print(f"[DEBUG CLEAN] Value is None, returning None")
        return None
    
    if isinstance(value, (int, float)):
        print(f"[DEBUG CLEAN] Value is numeric ({type(value)}), returning float: {float(value)}")
        return float(value)
    
    if not isinstance(value, str):
        print(f"[DEBUG CLEAN] Value is not a string (type: {type(value)}), returning None")
        return None
    
    # Remove currency symbols, text, keep only digits and decimal point
    cleaned = re.sub(r'[^\d.]', '', str(value))
    print(f"[DEBUG CLEAN] After removing non-digits: '{value}' -> '{cleaned}'")
    
    if not cleaned:
        print(f"[DEBUG CLEAN] Cleaned value is empty, returning None")
        return None
    
    try:
        result = float(cleaned)
        print(f"[DEBUG CLEAN] Converted to float: {result}")
        return result
    except ValueError as e:
        print(f"[DEBUG CLEAN] Conversion to float failed: {e}")
        return None


def extract_po_amount(text):
    """
    Extract PO total amount from document text.
    Field-aware extraction using labels like "Total Amount", "Grand Total", etc.
    
    Args:
        text (str): Document text
    
    Returns:
        float or None: Extracted amount
    """
    if not text:
        return None
    
    # Field-aware patterns with labels
    patterns = [
        r'(?:total\s+amount|grand\s+total|amount|net\s+amount|total\s+value|order\s+value|po\s+total)[:\s]+[\$€₹\w]*\s*([\d,]+(?:\.\d{1,2})?)',
        r'(?:total|amount)[:\s]+[\$€₹\w]*\s*([\d,]+(?:\.\d{1,2})?)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                continue
    
    return None


def extract_tax_amount(text):
    """
    Extract tax percentage from document text.
    
    Args:
        text (str): Document text
    
    Returns:
        int or None: Tax percentage
    """
    if not text:
        return None
    
    patterns = [
        r'(?:tax|vat|gst)[:\s]+(\d+)\s*%',
        r'@?\s*(\d+)\s*%\s*(?:VAT|tax|GST)',
        r'(\d+)\s*%\s*(?:VAT|tax|GST)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    
    return None
