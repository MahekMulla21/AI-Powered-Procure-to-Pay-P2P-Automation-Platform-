import sys
import os

# Add paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

from Invoice_processing.Invoice_rule_based_extractor import _extract_client_name

# Simulated text from OCR/DOCX based on the image
text = """
INVOICE
Enterprise Data Migration – STC Core Systems
Invoice Number: INV-001 | Invoice Date: April 05, 2024
-------------------------------------------------------
PO Ref: PO-STC-IT-2024-0047 | GRN Ref: GRN-001 | SOW: SOW-TCS-STC-DM-2024-001
| MSA: MSA-TCS-STC-2024-001
-------------------------------------------------------
BILL TO / CLIENT                          BILLED BY / VENDOR
Saudi Telecom Company (STC)               Tata Consultancy Services Ltd. (TCS)
P.O. Box 87, Riyadh 11432                 TCS House, Raveline Street, Fort
Kingdom of Saudi Arabia                   Mumbai – 400001, Maharashtra, India
"""

client = _extract_client_name(text)
print(f"Extracted Client: '{client}'")

if client == "Saudi Telecom Company (STC)":
    print("SUCCESS")
else:
    # Try another layout variant (some OCRs might combine lines)
    text2 = """
BILL TO / CLIENT
/ CLIENT
Saudi Telecom Company (STC)
"""
    client2 = _extract_client_name(text2)
    print(f"Extracted Client 2: '{client2}'")
    if client2 == "Saudi Telecom Company (STC)":
        print("SUCCESS (Variant 2)")
    else:
        print("FAILED")
