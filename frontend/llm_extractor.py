import requests
import json
import re

OLLAMA_URL = "http://localhost:11434/api/generate"


# =========================
# PROMPT
# =========================
def build_prompt(fields, text):

    fields_str = "\n".join(f"- {f}" for f in fields)

    return f"""
Extract ONLY the following fields in STRICT JSON:

{fields_str}

RULES:
- Output ONLY valid JSON
- No explanation
- No markdown
- Use null if missing
- Dates → YYYY-MM-DD
- Numbers → NO commas

LOGIC:
- Quantity = sum of (LS + Hr)
- Unit price = main service price (NOT hourly)
- End date from: Valid Until / End Date / Completion Date / Contract End

TEXT:
{text}
"""


# =========================
# CLEAN RESPONSE
# =========================
def clean_json_response(raw_text):

    raw_text = re.sub(r"```json|```", "", raw_text)

    start = raw_text.find("{")
    end = raw_text.rfind("}") + 1

    if start != -1 and end != -1:
        raw_text = raw_text[start:end]

    raw_text = re.sub(r'(\d),(?=\d{3})', r'\1', raw_text)
    raw_text = raw_text.replace("\n", " ")
    raw_text = raw_text.replace("N/A", "null")
    raw_text = raw_text.replace("–", "-")

    return raw_text.strip()


# =========================
# SAFE LOAD
# =========================
def safe_json_load(text):

    try:
        return json.loads(text)
    except:
        return {}


# =========================
# FINANCIAL FALLBACK LOGIC
# =========================
def extract_financials(text):

    total_match = re.search(r"(Total|Grand Total).*?([\d,]+\.\d+)", text, re.I)

    if total_match:
        total = float(total_match.group(2).replace(",", ""))

        phases = re.findall(r"Phase\s+(\d+)", text, re.I)
        qty = len(set(phases))

        unit = total / qty if qty else None

        return unit, qty, total

    return None, None, None


# =========================
# POST PROCESS (MAIN FIX)
# =========================

    # -------------------------
    # 🔥 FINAL FALLBACK (YOUR LOGIC)
    # -------------------------
    if not data.get("quantity") or not data.get("unit_price"):
        unit, qty_calc, total = extract_financials(text)

        if not data.get("quantity") and qty_calc:
            data["quantity"] = qty_calc

        if not data.get("unit_price") and unit:
            data["unit_price"] = unit

        if not data.get("total_amount") and total:
            data["total_amount"] = total

    return data


# =========================
# FIELD MAP
# =========================
FIELDS_MAP = {
    "PO": [
        "po_number", "po_date", "vendor_name", "client_name",
        "payment_terms", "delivery_terms", "currency",
        "total_amount", "start_date", "end_date",
        "reference_sow", "reference_msa",
        "description_of_goods_and_services",
        "quantity", "unit_price", "tax", "tax_breakup",
        "service_code", "delivery_location",
        "grn_indicator", "po_status"
    ]
}


# =========================
# MAIN FUNCTION
# =========================
def extract_fields(text, doc_type):

    fields = FIELDS_MAP.get(doc_type, [])

    if not fields:
        return {}

    prompt = build_prompt(fields, text)

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        })

        raw_output = response.json().get("response", "")
        print("\n🔹 RAW OUTPUT:\n", raw_output)

        cleaned = clean_json_response(raw_output)
        print("\n🧹 CLEANED TEXT:\n", cleaned)

        data = safe_json_load(cleaned)

        data = post_process(data, text)

        print("\n✅ FINAL PARSED DATA:\n", data)

        return data

    except Exception as e:
        print("❌ Extraction error:", e)
        return {}