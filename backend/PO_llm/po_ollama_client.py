import json
import ollama

from PO_config.po_settings import MODEL_NAME


def call_llm(prompt):
    """
    Call Ollama LLM safely with strict JSON mode.
    """

    print("\n[LLM] Calling Ollama...\n")

    try:

        # ============================================================
        # LLM CALL
        # ============================================================

        response = ollama.chat(
            model=MODEL_NAME,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            # Force deterministic output
            options={
                "temperature": 0
            },

            # Force JSON output
            format="json"
        )

        # ============================================================
        # EXTRACT CONTENT
        # ============================================================

        content = response.get("message", {}).get("content", "")

        if not content:

            print("[LLM] Empty response received")

            return json.dumps({
                "structured": {},
                "unstructured": {}
            })

        content = str(content).strip()

        print("✅ LLM Response received\n")

        # ============================================================
        # VALIDATE JSON FORMAT
        # ============================================================

        try:

            parsed = json.loads(content)

            if not isinstance(parsed, dict):
                raise ValueError("LLM response is not a JSON object")

            # Ensure required structure
            if "structured" not in parsed:
                parsed["structured"] = {}

            if "unstructured" not in parsed:
                parsed["unstructured"] = {}

            return json.dumps(parsed)

        except Exception as parse_error:

            print(f"[LLM] JSON validation failed: {parse_error}")

            print("\n========== RAW LLM RESPONSE ==========")
            print(content[:3000])
            print("========== END RESPONSE ==========\n")

            return json.dumps({
                "structured": {},
                "unstructured": {}
            })

    except Exception as e:

        print(f"\n❌ LLM ERROR: {e}\n")

        return json.dumps({
            "structured": {},
            "unstructured": {}
        })