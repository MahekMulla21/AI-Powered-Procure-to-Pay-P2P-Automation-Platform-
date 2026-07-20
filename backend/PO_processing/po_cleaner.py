import json
import re


def clean_json(response):
    """
    Safe and robust JSON cleaner for LLM responses.
    Handles:
    - markdown blocks
    - extra text before/after JSON
    - None/null issues
    - malformed whitespace
    """

    # ============================================================
    # EMPTY RESPONSE
    # ============================================================

    if not response:

        return {
            "structured": {},
            "unstructured": {}
        }

    try:

        # ============================================================
        # STEP 1: CONVERT TO STRING
        # ============================================================

        response = str(response).strip()

        # ============================================================
        # STEP 2: REMOVE MARKDOWN CODE BLOCKS
        # ============================================================

        response = re.sub(
            r"^```(?:json)?\s*",
            "",
            response,
            flags=re.IGNORECASE
        )

        response = re.sub(
            r"\s*```$",
            "",
            response
        )

        response = response.strip()

        # ============================================================
        # STEP 3: EXTRACT JSON OBJECT SAFELY
        # ============================================================

        json_match = re.search(
            r"\{.*\}",
            response,
            re.DOTALL
        )

        if not json_match:
            raise ValueError("No JSON object found in response")

        json_str = json_match.group(0)

        # ============================================================
        # STEP 4: CLEAN WHITESPACE
        # ============================================================

        json_str = (
            json_str
            .replace("\n", " ")
            .replace("\r", " ")
            .replace("\t", " ")
        )

        # ============================================================
        # STEP 5: FIX PYTHON VALUES
        # ============================================================

        # Python None → JSON null
        json_str = re.sub(
            r':\s*None\b',
            ': null',
            json_str
        )

        # Python True → JSON true
        json_str = re.sub(
            r':\s*True\b',
            ': true',
            json_str
        )

        # Python False → JSON false
        json_str = re.sub(
            r':\s*False\b',
            ': false',
            json_str
        )

        # ============================================================
        # STEP 6: REMOVE INVALID CONTROL CHARS
        # ============================================================

        json_str = re.sub(
            r'[\x00-\x1F\x7F]',
            ' ',
            json_str
        )

        # ============================================================
        # STEP 7: FIX INVALID BACKSLASHES
        # ============================================================

        json_str = re.sub(
            r'\\(?!["\\/bfnrtu])',
            r'\\\\',
            json_str
        )

        # ============================================================
        # STEP 8: PARSE JSON
        # ============================================================

        parsed_data = json.loads(json_str)

        # ============================================================
        # STEP 9: ENSURE REQUIRED STRUCTURE
        # ============================================================

        if not isinstance(parsed_data, dict):

            raise ValueError("Parsed JSON is not a dictionary")

        if "structured" not in parsed_data:
            parsed_data["structured"] = {}

        if "unstructured" not in parsed_data:
            parsed_data["unstructured"] = {}

        if parsed_data["structured"] is None:
            parsed_data["structured"] = {}

        if parsed_data["unstructured"] is None:
            parsed_data["unstructured"] = {}

        # ============================================================
        # SUCCESS
        # ============================================================

        return parsed_data

    except Exception as e:

        print("\n❌ FINAL JSON CLEAN FAILED")
        print("ERROR:", str(e))

        print("\n========== RAW RESPONSE ==========")

        try:
            print(response[:3000])
        except Exception:
            print("Unable to print response")

        print("\n========== END RAW RESPONSE ==========")

        return {
            "structured": {},
            "unstructured": {}
        }