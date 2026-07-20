import json
import re

from PR_llm.PR_prompt_template import get_prompt
from PR_llm.PR_ollama_client import call_llm


# ==================================================
# VALIDATE JSON
# ==================================================
def is_valid_json(text):

    try:

        start = text.find("{")

        end = text.rfind("}") + 1

        if start == -1 or end == -1:
            return False

        json.loads(text[start:end])

        return True

    except Exception:
        return False


# ==================================================
# CLEAN RESPONSE
# ==================================================
def clean_response(response):

    if not response:
        return "{}"

    response = response.strip()

    # Remove markdown
    response = re.sub(
        r"^```(?:json)?",
        "",
        response,
        flags=re.IGNORECASE
    )

    response = response.replace("```", "")

    # Remove extra spaces
    response = re.sub(r"\s+", " ", response)

    return response.strip()


# ==================================================
# EXTRACT FIELDS
# ==================================================
def extract_fields(text, rule_data):

    """
    Calls LLM with retry + validation
    """

    try:

        # ==================================================
        # STEP 1: BUILD PROMPT
        # ==================================================
        prompt = get_prompt(
            text,
            rule_data
        )

        # ==================================================
        # STEP 2: RETRY MECHANISM
        # ==================================================
        max_retries = 3

        for attempt in range(max_retries):

            print(
                f"\n🚀 LLM Attempt {attempt + 1}/{max_retries}\n"
            )

            # ==================================================
            # CALL LLM
            # ==================================================
            response = call_llm(prompt)

            # ==================================================
            # EMPTY RESPONSE
            # ==================================================
            if not response:

                print("⚠️ Empty LLM response")

                continue

            # ==================================================
            # CLEAN RESPONSE
            # ==================================================
            response = clean_response(response)

            # ==================================================
            # VALIDATE JSON
            # ==================================================
            if is_valid_json(response):

                print("✅ Valid JSON received")

                return response

            print("⚠️ Invalid JSON received")

        # ==================================================
        # FAILED AFTER RETRIES
        # ==================================================
        print("❌ Failed after retries")

        return "{}"

    except Exception as e:

        print(
            "❌ LLM extraction failed:",
            str(e)
        )

        return "{}"