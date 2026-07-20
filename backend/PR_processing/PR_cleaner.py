import json
import re


# ===============================
# STRUCTURED FIELD NAMES
# ===============================
STRUCTURED_FIELDS = {
    "pr_id",
    "request_date",
    "requested_by",
    "requestor_title",
    "department",
    "vendor_name",
    "budget_code",
    "priority",
    "total_amount",
    "currency",
    "required_date",
    "reference_sow_number",
    "reference_msa_number",
    "approval_status",
    "service_code",
    "purchasing_group",
}

# ===============================
# UNSTRUCTURED FIELD NAMES
# ===============================
UNSTRUCTURED_FIELDS = {
    "quantity",
    "location",
    "description",
}


# ===============================
# CLEAN FIELD VALUE
# ===============================
def clean_field_value(field, value):

    if not isinstance(value, str):
        return value

    # Remove line breaks
    value = value.replace("\n", " ")
    value = value.replace("\r", " ")
    value = value.replace("\t", " ")

    # Normalize spaces
    value = re.sub(r"\s+", " ", value)

    # ==========================================
    # FIELD-SPECIFIC CLEANUP
    # ==========================================

    # ------------------------------
    # pr_id cleanup
    # ------------------------------
    if field == "pr_id":

        value = re.sub(
            r"\s*Date.*",
            "",
            value,
            flags=re.IGNORECASE
        )

        match = re.search(
            r"(PR[-A-Z0-9\/]+)",
            value,
            re.IGNORECASE
        )

        if match:
            value = match.group(1)

    # ------------------------------
    # description cleanup
    # ------------------------------
    if field == "description":

        stop_words = [
            "APPROVAL",
            "VENDOR",
            "BUDGET",
            "PAYMENT",
            "PURCHASING GROUP",
            "PRIORITY",
            "LOCATION",
            "SERVICE CODE"
        ]

        for stop_word in stop_words:

            value = re.split(
                rf"\b{stop_word}\b",
                value,
                flags=re.IGNORECASE
            )[0]

    # ------------------------------
    # vendor_name cleanup
    # ------------------------------
    if field == "vendor_name":

        value = re.sub(
            r"\b(Address|Location|Phone|Registration)\b.*",
            "",
            value,
            flags=re.IGNORECASE
        )

    # ------------------------------
    # total_amount cleanup
    # ------------------------------
    if field == "total_amount":

        value = re.sub(r"[₹$€£]", "", value)

        value = re.sub(
            r"\b(USD|INR|EUR|GBP|Amount|Total)\b",
            "",
            value,
            flags=re.IGNORECASE
        )

        value = value.replace(",", "")
        value = value.strip()

    # ------------------------------
    # currency cleanup
    # ------------------------------
    if field == "currency":

        match = re.search(
            r"\b(USD|INR|EUR|GBP)\b",
            value,
            re.IGNORECASE
        )

        if match:
            value = match.group(1).upper()

        else:
            symbol_map = {
                "$": "USD",
                "₹": "INR",
                "€": "EUR",
                "£": "GBP"
            }
            symbol_match = re.search(r"[₹$€£]", value)

            if symbol_match:
                value = symbol_map.get(
                    symbol_match.group(0),
                    value
                )

    # ------------------------------
    # priority cleanup
    # ------------------------------
    if field == "priority":

        match = re.search(
            r"\b(High|Medium|Low)\b",
            value,
            re.IGNORECASE
        )

        if match:
            value = match.group(1).capitalize()

    # ------------------------------
    # approval_status cleanup
    # ------------------------------
    if field == "approval_status":

        match = re.search(
            r"\b(Pending|Approved|Rejected)\b",
            value,
            re.IGNORECASE
        )

        if match:
            value = match.group(1).capitalize()

    # ------------------------------
    # requested_by cleanup
    # ------------------------------
    if field == "requested_by":

        parts = re.split(r"\s{2,}|\t", value)
        value = parts[0].strip()

        value = re.sub(
            r"\s+(Director|Manager|Engineer|Officer|Head|Lead|Analyst|Executive|VP|CTO|CFO|CEO)$",
            "",
            value,
            flags=re.IGNORECASE
        ).strip()

    # ------------------------------
    # request_date / required_date cleanup
    # ------------------------------
    if field in ("request_date", "required_date"):

        value = re.sub(
            r"\b(Request Date|Required Date|Date)\b[:\-]?\s*",
            "",
            value,
            flags=re.IGNORECASE
        )

    # ------------------------------
    # reference_sow_number cleanup
    # ------------------------------
    if field == "reference_sow_number":

        value = re.sub(
            r"\s*Date.*",
            "",
            value,
            flags=re.IGNORECASE
        )

        match = re.search(
            r"(SOW[-A-Z0-9\/]+)",
            value,
            re.IGNORECASE
        )

        if match:
            value = match.group(1)

    # ------------------------------
    # reference_msa_number cleanup
    # ------------------------------
    if field == "reference_msa_number":

        value = re.sub(
            r"\s*Date.*",
            "",
            value,
            flags=re.IGNORECASE
        )

        match = re.search(
            r"(MSA[-A-Z0-9\/]+)",
            value,
            re.IGNORECASE
        )

        if match:
            value = match.group(1)

    return value.strip()


# ===============================
# NORMALIZE LLM RESPONSE
# ===============================
def normalize_llm_response(data):

    """
    The LLM returns one of 3 formats. This function
    always produces clean nested structured/unstructured.

    Case 1 — Clean nested (LLM followed the prompt):
        { "structured": { "pr_id": "X", ... },
          "unstructured": { ... } }
        → used as-is

    Case 2 — Mixed (nested block exists but values are None,
              AND flat keys also present at top level):
        { "structured": { "pr_id": null, ... },
          "pr_id": "X", "vendor_name": "Y", ... }
        → flat keys win, merged over nested block

    Case 3 — Flat (LLM ignored nesting instruction):
        { "pr_id": "X", "vendor_name": "Y", ... }
        → rebuilt into nested format
    """

    structured_block = data.get("structured", {})
    unstructured_block = data.get("unstructured", {})

    if not isinstance(structured_block, dict):
        structured_block = {}

    if not isinstance(unstructured_block, dict):
        unstructured_block = {}

    # Check if nested structured block has real non-None values
    nested_has_values = any(
        v is not None
        for v in structured_block.values()
    )

    # Collect flat structured keys sitting at top level
    flat_structured = {
        k: v for k, v in data.items()
        if k not in ("structured", "unstructured")
        and k in STRUCTURED_FIELDS
    }

    # Collect flat unstructured keys sitting at top level
    flat_unstructured = {
        k: v for k, v in data.items()
        if k not in ("structured", "unstructured")
        and k in UNSTRUCTURED_FIELDS
    }

    if nested_has_values and not flat_structured:
        # Case 1: Clean nested — pass through as-is
        return {
            "structured": structured_block,
            "unstructured": unstructured_block
        }

    if flat_structured:
        # Case 2 + 3: Flat keys exist — flat takes priority
        # Merge: start with nested block, override with flat values
        merged_structured = {**structured_block, **flat_structured}
        merged_unstructured = {**unstructured_block, **flat_unstructured}
        return {
            "structured": merged_structured,
            "unstructured": merged_unstructured
        }

    # Fallback: return whatever nested blocks we have
    return {
        "structured": structured_block,
        "unstructured": unstructured_block
    }


# ===============================
# CLEAN STRUCTURED DATA
# ===============================
def clean_structured_data(data):

    structured = data.get("structured", {})

    for key, value in structured.items():
        structured[key] = clean_field_value(key, value)

    # approval_status must never be null or empty
    if not structured.get("approval_status"):
        structured["approval_status"] = "Pending"

    # currency: store None if genuinely missing
    if structured.get("currency") == "":
        structured["currency"] = None

    # service_code / purchasing_group: None not empty string
    if structured.get("service_code") == "":
        structured["service_code"] = None

    if structured.get("purchasing_group") == "":
        structured["purchasing_group"] = None

    data["structured"] = structured

    return data


# ===============================
# CLEAN UNSTRUCTURED DATA
# ===============================
def clean_unstructured_data(data):

    unstructured = data.get("unstructured", {})

    for key, value in unstructured.items():

        # quantity is JSONB — skip string cleanup
        if key == "quantity":

            if isinstance(value, dict):
                unstructured[key] = value

            elif isinstance(value, str):
                try:
                    unstructured[key] = json.loads(value)
                except Exception:
                    unstructured[key] = {}

            continue

        if isinstance(value, str):
            value = value.replace("\n", " ")
            value = re.sub(r"\s+", " ", value)
            stripped = value.strip()
            unstructured[key] = stripped if stripped else None

        elif value is None:
            unstructured[key] = None

    if unstructured.get("location") == "":
        unstructured["location"] = None

    data["unstructured"] = unstructured

    return data


# ===============================
# MAIN CLEANER
# ===============================
def clean_json(response):

    """
    Robust JSON cleaner for messy LLM output.
    Handles flat, nested, and mixed LLM responses.
    """

    if not response:
        return {
            "structured": {},
            "unstructured": {}
        }

    try:

        # ===============================
        # STEP 1: Extract JSON Block
        # ===============================
        start = response.find("{")
        end = response.rfind("}") + 1

        if start == -1 or end == -1:
            raise ValueError("No JSON found")

        json_str = response[start:end]

        # ===============================
        # STEP 2: BASIC CLEANUP
        # ===============================
        json_str = json_str.replace(": None", ": null")
        json_str = json_str.replace(":None", ": null")
        json_str = json_str.replace(": True", ": true")
        json_str = json_str.replace(": False", ": false")
        json_str = json_str.replace("```json", "")
        json_str = json_str.replace("```", "")
        json_str = json_str.replace("\n", " ")
        json_str = json_str.replace("\r", " ")
        json_str = json_str.replace("\t", " ")
        json_str = re.sub(r"\s+", " ", json_str)

        # ===============================
        # FIX INVALID BACKSLASHES
        # ===============================
        json_str = re.sub(
            r'\\(?!["\\/bfnrt])',
            r'\\\\',
            json_str
        )

        # ===============================
        # FIX TRAILING COMMAS
        # ===============================
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)

        # ===============================
        # STEP 3: PARSE JSON
        # ===============================
        data = json.loads(json_str)

        # ===============================
        # STEP 4: NORMALIZE STRUCTURE
        # Handles flat / nested / mixed
        # ===============================
        data = normalize_llm_response(data)

        # ===============================
        # STEP 5: CLEAN STRUCTURED DATA
        # ===============================
        data = clean_structured_data(data)

        # ===============================
        # STEP 6: CLEAN UNSTRUCTURED DATA
        # ===============================
        data = clean_unstructured_data(data)

        return data

    except Exception as e:

        print("❌ FINAL JSON CLEAN FAILED:", str(e))

        return {
            "structured": {},
            "unstructured": {}
        }