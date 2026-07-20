from MSA_llm.MSA_prompt_template import get_prompt
from MSA_llm.MSA_ollama_client import call_llm


def extract_fields(text, rule_data):
    """
    Calls LLM with prompt and returns cleaned raw response
    """

    try:
        # ===============================
        # STEP 1: Build Prompt
        # ===============================
        prompt = get_prompt(text, rule_data)

        # ===============================
        # STEP 2: Call LLM
        # ===============================
        print("🚀 Calling LLM...\n")
        response = call_llm(prompt)

        # ===============================
        # STEP 3: Basic Cleanup
        # ===============================
        if not response:
            print("⚠️ Empty LLM response")
            return "{}"

        response = response.strip()

        # Remove accidental markdown (just in case)
        if response.startswith("```"):
            response = response.strip("`")

        return response

    except Exception as e:
        print("❌ LLM extraction failed:", e)
        return "{}"