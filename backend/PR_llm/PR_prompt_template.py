import json


def get_prompt(text, rule_data):

    # FIX: Convert rule_data dict to readable JSON string
    # so the LLM can parse it cleanly instead of raw Python repr
    if isinstance(rule_data, dict):
        rule_data_str = json.dumps(rule_data, indent=2, default=str)
    else:
        rule_data_str = str(rule_data)

    return f"""
You are a STRICT enterprise Purchase Requisition (PR) extraction engine.

Your ONLY task is to extract structured and unstructured
fields from the provided Purchase Requisition document.

Your response must contain ONLY the JSON object.
Start your response with {{ and end with }}.
No introductory text. No explanation. No markdown.

==================================================
DOCUMENT TEXT
==================================================

{text}

==================================================
RULE-BASED EXTRACTION (PRIMARY SOURCE)
==================================================

{rule_data_str}

==================================================
CRITICAL EXTRACTION RULES
==================================================

1. RULE-BASED EXTRACTION is the PRIMARY source.
   Use these values directly unless they are null or empty.

2. DOCUMENT TEXT should ONLY be used for:
   - filling null or empty rule-based values
   - verification
   - correction

3. NEVER overwrite a non-null rule-based value
   with an uncertain value from the document.

4. Return ONLY ONE valid JSON object.

5. DO NOT return:
   - explanations
   - markdown
   - comments
   - notes
   - any text before or after the JSON

6. Output MUST work directly with:
   json.loads()

7. NEVER hallucinate fields or values.

8. If a field cannot be found anywhere:
   return null for structured fields.
   return {{}} for quantity.
   return null for location and description.

9. Preserve ORIGINAL casing.

10. Replace all line breaks with spaces.

11. Escape internal double quotes using \\"

12. NEVER merge nearby fields.

13. NEVER include section headings inside values.

14. STOP extraction before next section heading.

15. Remove OCR noise and unrelated text.

==================================================
STRICT FIELD RULES
==================================================

pr_id:
- Return ONLY the PR number/ID.
- NEVER include dates or labels.
- Correct Example:
  "PR-2024-00123"
- Wrong Example:
  "PR-2024-00123 Date: 01-Jan-2024"

--------------------------------------------------

request_date / required_date:
- Preserve original date format.
- Return ONLY the date value.
- NEVER include labels or surrounding text.

--------------------------------------------------

requested_by:
- Return ONLY the person's full name.
- Do NOT include designation, title, or department.
- If the value contains extra words after the name
  (e.g. "Sarah Mitchell IT Director"),
  return ONLY "Sarah Mitchell".

--------------------------------------------------

department:
- Return ONLY the department name.
- Do NOT include codes or addresses.

--------------------------------------------------

vendor_name:
- Return ONLY the vendor/supplier company name.
- Do NOT include addresses or registration numbers.

--------------------------------------------------

budget_code:
- Return ONLY the budget or cost center code.
- NEVER include descriptions.

--------------------------------------------------

priority:
- Return ONLY one of:
  High
  Medium
  Low
- Normalize casing accordingly.

--------------------------------------------------

total_amount:
- Return ONLY the numeric value (no currency symbol, no label).
- The document may store this in a TABLE CELL, not a plain text line.
  Look carefully in ALL of these places:
    * A two-column table row: "Total Amount | USD 950,000.00"
    * A two-column table row: "Total PR Value | USD 950,000.00"
    * The TOTAL row at the bottom of the line items table:
      "TOTAL CONTRACT VALUE (USD) | $950,000.00"
    * Any labeled row: "Total Amount:", "Grand Total:", "PR Value:"
    * A standalone number preceded by a currency symbol ($, ₹, €, £)
- Strip the currency code/symbol and commas before returning.
- If the rule-based value for total_amount is null,
  search the DOCUMENT TEXT carefully using the above locations.
- Correct Example:
  "950000.00"
- Wrong Example:
  "USD 950,000.00"
- If genuinely not present anywhere in the document, return null.

--------------------------------------------------

currency:
- Return ONLY one of:
  USD
  INR
  EUR
  GBP
- Look for currency symbols in the document:
  $ = USD
  ₹ = INR
  € = EUR
  £ = GBP
- If no currency found anywhere, return null.

--------------------------------------------------

reference_sow_number:
- Return ONLY the SOW reference number.
- NEVER include dates or labels.

--------------------------------------------------

reference_msa_number:
- Return ONLY the MSA reference number.
- NEVER include dates or labels.

--------------------------------------------------

approval_status:
- Return ONLY the current approval status.
- Accepted values:
  Pending
  Approved
  Rejected
- If no approval status is mentioned in the document,
  return "Pending" as the default.
- NEVER return null or empty string for this field.

--------------------------------------------------

service_code:
- Return ONLY a short alphanumeric service, item, or product code.
- The document may have a LINE ITEMS TABLE with a "Service Code" column.
  Look for pipe-delimited table cells like:
    | SVC-DM-001 | Discovery & Assessment ... |
  The code is always in its OWN cell, short, hyphenated, e.g.:
    SVC-DM-001, SVC-DM-002, IT-MIG-01, SKU-12345
- Return the FIRST valid service code found in the table.
- STRICT REJECTION RULES — return null if the candidate value:
    * Is longer than 40 characters
    * Contains a comma
    * Reads like a sentence or description
    * Contains words like "quantity", "unit price", "milestone",
      "linked", "and", "the", "table", "below", "details"
- If the rule-based value looks like a sentence or description,
  IGNORE it completely and search the DOCUMENT TEXT for a short code.
- If no valid short code exists anywhere in the document, return null.
- NEVER return descriptive text as a service code.
- Correct Example:
  "SVC-DM-001"
- Wrong Example:
  ", quantity, unit price, and linked project milestone as"

--------------------------------------------------

purchasing_group:
- Return ONLY the purchasing group name or code.
- If not present in the document, return null.

--------------------------------------------------

quantity:
- Return as a JSON object using the ACTUAL item/service name
  as the key, not generic names like item_1 or item_2.
- The document has a LINE ITEMS TABLE. Read it carefully:
    | # | Service Code | Description | Qty | UoM | Unit Price | Total | Milestone |
  Use the Description column as the key, Qty column as the value.
- Correct Example:
  {{
    "Discovery & Assessment": 1,
    "Architecture & Design": 1,
    "Pilot Migration": 1,
    "Full Production Migration": 1,
    "Stabilization & Hypercare": 1
  }}
- Wrong Example:
  {{"item_1": 1, "item_2": 1, "item_3": 1}}
- If no items found, return {{}}.

--------------------------------------------------

location:
- Return ONLY the delivery or service location.
- Do NOT include postal codes unless part of original.
- If not present in the document, return null.

--------------------------------------------------

description:
- Return ONLY the PR description or purpose text.
- Replace all line breaks with spaces.
- Stop before next section heading.
- If not present, return null.

==================================================
OUTPUT FORMAT
==================================================

{{
  "request_date": "",
  "currency": "",
  "requested_by": "",
  "requestor_title": null,
  "required_date": "",
  "pr_id": "",
  "reference_sow_number": "",
  "reference_msa_number": "",
  "priority": "",
  "approval_status": "Pending",
  "description": "",
  "quantity": {{}},
  "location": null,
  "department": "",
  "vendor_name": "",
  "budget_code": "",
  "service_code": null,
  "purchasing_group": null,
  "total_amount": null
}}

==================================================
FINAL INSTRUCTIONS
==================================================

- Return ONLY valid JSON.
- No markdown.
- No ```json
- No explanations.
- No additional text.
- Your entire response = the JSON object only.
- For service_code: look in the line items table for a short code like SVC-DM-001.
  If in doubt, return null. A wrong null is better than garbage text.
- For total_amount: check table cells and the TOTAL CONTRACT VALUE row
  before returning null. Strip currency symbols and commas from the value.
"""