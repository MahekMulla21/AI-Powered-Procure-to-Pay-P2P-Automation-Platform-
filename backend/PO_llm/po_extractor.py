import re
from PO_llm.po_prompt_template import get_prompt
from PO_llm.po_ollama_client import call_llm


def extract_fields(text, rule_data):
    """
    Calls LLM with prompt and returns cleaned raw JSON response.
    """

    try:
        # ===============================
        # STEP 1: Build Prompt
        # ===============================
        prompt = get_prompt(text, rule_data)

        # ===============================
        # STEP 2: Call LLM
        # ===============================
        print("[LLM] Sending prompt to model...")
        response = call_llm(prompt)

        # ===============================
        # STEP 3: Validate Response
        # ===============================
        if not response or not response.strip():
            print("[WARN] Empty LLM response received")
            return "{}"

        response = response.strip()

        # ===============================
        # STEP 4: Strip Markdown Fences
        # e.g. ```json ... ``` or ``` ... ```
        # ===============================
        response = re.sub(r"^```(?:json)?\s*", "", response)
        response = re.sub(r"\s*```$",          "", response)
        response = response.strip()

        # ===============================
        # STEP 5: Extract JSON block
        # Safeguard if LLM adds text before/after JSON
        # ===============================
        json_match = re.search(r"\{.*\}", response, re.DOTALL)

        if not json_match:
            print("[WARN] No JSON block found in LLM response")
            print("[DEBUG] Raw response:", response[:300])
            return "{}"

        response = json_match.group(0).strip()

        print("[LLM] Response received and cleaned successfully")
        return response

    except Exception as e:
        print(f"[ERROR] LLM extraction failed: {e}")
        return "{}"