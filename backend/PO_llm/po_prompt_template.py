def get_prompt(text, rule_data):
    return f"""
You are a STRICT JSON extractor.

INPUT TEXT:
{text}

PRE-EXTRACTED DATA:
{rule_data}

TASK:
- Extract and verify data
- Fill missing fields

STRICT RULES:
- Return ONLY ONE JSON
- NO explanation
- NO markdown
- NO text outside JSON
- Escape ALL double quotes inside values using backslash (\")
- Replace line breaks with space
- Output must be valid for json.loads()

SERVICE_CODE EXTRACTION RULES:
- Extract "service_code" ONLY if an explicit code is present in the document
- Valid service_code format examples: IT-DT-CAPEX-2024-DM-007, SC-12345, CODE-XXXX, SVC-DM-001
- DO NOT guess or generate service_code
- DO NOT return descriptions like "quantity unit price and linked project"
- DO NOT return plain text descriptions
- If no valid service_code is found, return null

TOTAL_AMOUNT EXTRACTION RULES:
- Extract the FINAL TOTAL amount (including tax), NOT the subtotal
- Look for labels like "Total Amount", "Grand Total", "Total Value", "Order Total"
- If amount includes tax notation like "(@ 15% VAT)", extract the full amount before the tax notation
- DO NOT extract subtotal or line item amounts
- Return the full numeric amount as a string (e.g., "1092500.00")

TABLE EXTRACTION RULES (CRITICAL):
- PO line items often appear in tables with multiple rows (like the example below)
- Extract ALL rows from the table, not just the first one
- Count the number of rows in the table and return that many values in each array
- For tabular fields, ALWAYS return as JSON ARRAY (even if only one row)
- Fields that MUST be arrays: service_code, quantity, unit_price, tax

EXAMPLE TABLE FORMAT:
| # | Service Code | Description | Qty | Unit Price (USD) | Total (USD) | Milestone |
|---|--------------|-------------|-----|------------------|-------------|-----------|
| 1 | SVC-DM-001 | Discovery & Assessment | 2 LS | $120,000.00 | $120,000.00 | M1 |
| 2 | SVC-DM-002 | Architecture & Design | 1 LS | $180,000.00 | $180,000.00 | M2 |
| 3 | SVC-DM-003 | Pilot Migration | 5 LS | $200,000.00 | $200,000.00 | M3 |
| 4 | SVC-DM-004 | Full Production Migration | 1 LS | $320,000.00 | $320,000.00 | M4 |
| 5 | SVC-DM-005 | Stabilization & Hypercare | 6 LS | $130,000.00 | $130,000.00 | M5 |

For this table, return:
- service_code: ["SVC-DM-001", "SVC-DM-002", "SVC-DM-003", "SVC-DM-004", "SVC-DM-005"]
- quantity: [2, 1, 5, 1, 6] (extract the number before "LS")
- unit_price: [120000, 180000, 200000, 320000, 130000]
- tax: [15, 15, 15, 15, 15] (if VAT is 15%)

service_code extraction:
- Look for table column headers: "Service Code", "Code", "Item Code", "S.No"
- Extract ALL service codes from ALL rows (count the rows!)
- Return as JSON array: ["SVC-DM-001", "SVC-DM-002", "SVC-DM-003", "SVC-DM-004", "SVC-DM-005"]

quantity extraction:
- Look for table column headers: "Quantity", "Qty", "Units"
- Extract ALL quantities from ALL rows (one per row)
- If quantity shows "2 LS" (Lump Sum), extract just the number: 2
- Remove "LS" text, keep only numeric values
- Return as JSON array: [2, 1, 5, 1, 6]

unit_price extraction:
- Look for table column headers: "Unit Price", "Rate", "Price"
- Extract ALL unit prices from ALL rows
- Remove currency symbols ($, USD, ₹, €)
- Remove commas, keep only numeric values
- Return as JSON array: [120000, 180000, 200000, 320000, 130000]

tax extraction:
- Look for table column headers: "Tax", "VAT", "GST", "Tax %"
- Look for tax percentage in document (e.g., "@ 15% VAT", "VAT 15%")
- Extract ALL tax values from ALL rows
- Return percentage values as numbers (e.g., 15 for 15%)
- Return as JSON array: [15, 15, 15, 15, 15]

CRITICAL FORMAT RULES:
1. ALWAYS return arrays for: service_code, quantity, unit_price, tax
2. Arrays must have same length (one value per table row)
3. Remove currency symbols: $, USD, INR, €, ₹
4. Remove commas from numbers: 1,092,500 → 1092500
5. Convert to numeric format where applicable
6. If a specific value in a row is not found → use null in that array position (NOT empty string "")
7. If entire field not found → return null (not empty array, not empty string)
8. NEVER return empty strings "" inside arrays
9. Arrays should contain actual values or null, never empty strings
10. Output values must be VALID JSON strings that can be parsed with json.loads()

WRONG (empty strings in arrays):
"quantity": [""], "unit_price": ["", "", ""]

CORRECT (null for missing values):
"quantity": [null], "unit_price": [120000, null, 150000]

CORRECT (null if entire field missing):
"quantity": null, "unit_price": null

EXAMPLE OUTPUT:
{{
  "structured": {{
    "po_id": "PO-2024-001",
    "po_date": "2024-01-15",
    "vendor_name": "ABC Corp",
    "client_name": "XYZ Inc",
    "payment_terms": "Net 30",
    "delivery_terms": "FOB",
    "currency": "USD",
    "total_amount": "1092500.00",
    "start_date": "2024-01-15",
    "end_date": "2024-12-31",
    "reference_sow": "SOW-2024-001",
    "reference_msa": "MSA-2024-001",
    "quantity": "[2, 1, 5, 1, 6]",
    "unit_price": "[120000, 180000, 200000, 320000, 130000]",
    "tax": "[15, 15, 15, 15, 15]",
    "tax_breakup": "{{}}",
    "service_code": "[\"SVC-DM-001\", \"SVC-DM-002\", \"SVC-DM-003\", \"SVC-DM-004\", \"SVC-DM-005\"]",
    "delivery_location": "",
    "grn_indicator": "",
    "po_status": ""
  }},
  "unstructured": {{
    "description_of_goods_and_services": "IT consulting services..."
  }}
}}

Correct escaping:
"description_of_service": "The vendor shall provide \\"IT consulting services\\" as outlined..."

Wrong:
"description_of_service": "The vendor shall provide "IT consulting services" as outlined..."

OUTPUT FORMAT:

{{
  "structured": {{
    "po_id": "",
    "po_date": "",
    "vendor_name": "",
    "client_name": "",
    "payment_terms": "",
    "delivery_terms": "",
    "currency": "",
    "total_amount": "",
    "start_date": "",
    "end_date": "",
    "reference_sow": "",
    "reference_msa": "",
    "quantity": "",
    "unit_price": "",
    "tax": "",
    "tax_breakup": "",
    "service_code": "",
    "delivery_location": "",
    "grn_indicator": "",
    "po_status": ""
  }},
  "unstructured": {{
    "description_of_goods_and_services": ""
  }}
}}
"""