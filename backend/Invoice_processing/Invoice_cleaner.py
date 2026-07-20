import json
import re

def clean_json(response):
    """
    Robust JSON cleaner for messy LLM output.
    Always returns a dict with 'structured' and 'unstructured' keys.
    """

    if not response:
        return {"structured": {}, "unstructured": {}}

    try:
        # ===============================
        # STEP 1: Extract JSON block
        # ===============================
        start = response.find("{")
        end = response.rfind("}") + 1

        if start == -1 or end == -1:
            raise ValueError("No JSON found")

        json_str = response[start:end]

        # ===============================
        # STEP 2: FIX ESCAPE ISSUES
        # ===============================

        # Fix Python None → JSON null
        json_str = json_str.replace(": None", ": null")
        json_str = json_str.replace(":None", ": null")

        # Remove newlines / tabs
        json_str = json_str.replace("\n", " ").replace("\r", " ").replace("\t", " ")

        # Fix unescaped backslashes
        json_str = re.sub(r'\\(?!["\\\/bfnrt])', r'\\\\', json_str)

        # Fix unescaped inner quotes
        json_str = re.sub(r':\s*"(.*?)"', lambda m: f': "{m.group(1).replace(chr(34), chr(92) + chr(34))}"', json_str)

        # ===============================
        # STEP 3: Parse JSON
        # ===============================
        parsed = json.loads(json_str)

        # ===============================
        # STEP 4: Normalise shape
        # Always return {"structured": {...}, "unstructured": {...}}
        # ===============================
        if not isinstance(parsed, dict):
            raise ValueError("Parsed JSON is not a dict")

        # If LLM returned a flat dict without our expected top-level keys,
        # auto-categorise the fields instead of discarding them.
        if "structured" not in parsed and "unstructured" not in parsed:
            _UNSTRUCTURED_KEYS = {
                "description_of_service", "tax_breakup", "bank_details",
            }
            structured   = {}
            unstructured = {}
            for k, v in parsed.items():
                if k in _UNSTRUCTURED_KEYS:
                    unstructured[k] = v
                else:
                    structured[k] = v

            # Only return the auto-wrapped result if it actually has data;
            # a truly empty {} still returns the empty default.
            if structured or unstructured:
                return {"structured": structured, "unstructured": unstructured}
            return {"structured": {}, "unstructured": {}}

        parsed.setdefault("structured", {})
        parsed.setdefault("unstructured", {})
        return parsed

    except Exception as e:
        print("FINAL JSON CLEAN FAILED:", e)

        return {
            "structured": {},
            "unstructured": {}
        }