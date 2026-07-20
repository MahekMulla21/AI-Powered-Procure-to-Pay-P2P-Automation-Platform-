import ollama
import re

from PR_config.PR_settings import MODEL_NAME, URL, API


def clean_llm_response(response_text):
    """
    Basic cleanup for raw LLM output
    """

    if not response_text:
        return "{}"

    response_text = response_text.strip()

    # Remove markdown blocks
    response_text = re.sub(
        r"^```(?:json)?",
        "",
        response_text,
        flags=re.IGNORECASE
    )

    response_text = response_text.replace("```", "")

    # Remove extra spaces
    response_text = re.sub(r"\s+", " ", response_text)

    return response_text.strip()


def call_llm(prompt, attempt=1):

    print(f"\n🚀 Calling LLM...\n")

    # On retry attempts, append a stronger instruction
    retry_suffix = ""

    if attempt == 2:
        retry_suffix = (
            "\n\nIMPORTANT: Your previous response failed JSON parsing. "
            "Return ONLY the raw JSON object. "
            "Start your response with { and end with }. "
            "Absolutely no other text."
        )

    elif attempt == 3:
        retry_suffix = (
            "\n\nCRITICAL: Return ONLY this exact structure with no other text:\n"
            '{"structured": {...}, "unstructured": {...}}'
        )

    final_prompt = prompt + retry_suffix

    try:

        response = ollama.chat(

            model=MODEL_NAME,

            messages=[
                # ===============================
                # FIX: System role message added
                # Forces JSON-only output and
                # eliminates preamble text
                # ===============================
                {
                    "role": "system",
                    "content": (
                        "You are a JSON extraction engine. "
                        "You output ONLY a single valid JSON object. "
                        "Your response must start with { and end with }. "
                        "No preamble. No explanation. No markdown. "
                        "No introductory sentences. "
                        "No text before or after the JSON."
                    )
                },
                {
                    "role": "user",
                    "content": final_prompt
                }
            ],

            # ===============================
            # DETERMINISTIC SETTINGS
            # ===============================
            options={

                # MOST IMPORTANT
                "temperature": 0,

                # Reduce randomness
                "top_p": 1,

                # Avoid repetition
                "repeat_penalty": 1,

                # Stable prediction
                "seed": 42,

                # Better extraction
                "num_predict": 2048
            }

        )

        print("✅ LLM Response received\n")

        content = response.get("message", {}).get("content", "")

        if not content:
            print("⚠️ Empty LLM response")
            return "{}"

        # ===============================
        # CLEAN RESPONSE
        # ===============================
        content = clean_llm_response(content)

        return content

    except Exception as e:

        print("❌ LLM ERROR:", str(e))

        return "{}"