import json
import re

def clean_json(response):
    """
    Robust JSON cleaner for messy LLM output
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

        # ✅ Fix Python None → JSON null
        json_str = json_str.replace(": None", ": null")
        json_str = json_str.replace(":None", ": null")

        # # ✅ Fix Python True/False → JSON true/false
        # json_str = json_str.replace(": True", ": true")
        # json_str = json_str.replace(": False", ": false")

        # Remove newlines / tabs
        json_str = json_str.replace("\n", " ").replace("\r", " ").replace("\t", " ")

        # Fix unescaped backslashes
        json_str = re.sub(r'\\(?!["\\/bfnrt])', r'\\\\', json_str)

        # 🔥 FIX UNESCAPED INNER QUOTES (KEY FIX)
        json_str = re.sub(r':\s*"(.*?)"', lambda m: f': "{m.group(1).replace(chr(34), r"\"")}"', json_str)

        # ===============================
        # STEP 3: Parse JSON
        # ===============================
        return json.loads(json_str)

    except Exception as e:
        print("❌ FINAL JSON CLEAN FAILED:", e)

        return {
            "structured": {},
            "unstructured": {}
        }