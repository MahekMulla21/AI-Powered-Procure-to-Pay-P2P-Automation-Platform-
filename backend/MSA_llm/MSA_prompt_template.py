def get_prompt(text, rule_data):

    return f"""You are a JSON extraction engine. Output ONLY a JSON object. No text before or after.

========================
RULE-BASED EXTRACTION (PRIMARY SOURCE)
========================
{rule_data}

========================
DOCUMENT TEXT (USE ONLY FOR MISSING/VERIFICATION)
========================
{text}

========================
STRICT RULES
========================
- Output MUST start with {{ and end with }}
- NO markdown, NO backticks, NO headers, NO explanations
- NO text before the opening {{ or after the closing }}
- Replace all line breaks inside values with a space
- Escape internal double quotes with \\"
- If field not found: use empty string ""
- Do NOT hallucinate values
- Preserve original casing
- msa_id: return ONLY the agreement ID, no dates or labels
- termination_clause: stop before next section heading
- payment_terms: return ONLY the payment terms sentence
- vendor_name: return ONLY the company name

========================
OUTPUT (return exactly this structure, filled in)
========================
{{"structured":{{"vendor_name":"","vendor_id":"","start_date":"","end_date":"","currency":"","status":"","created_by":"","payment_terms":"","termination_clause":"","msa_id":""}},"unstructured":{{"intellectual_property":"","dispute_resolution":"","confidentiality":"","liability_clause":"","indemnification_clause":""}}}}
"""