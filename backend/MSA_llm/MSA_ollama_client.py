# MSA_ollama_client.py

import ollama
from MSA_config.MSA_settings import MODEL_NAME

def call_llm(prompt):
    print("\n🚀 Calling LLM...\n")

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            format="json",          # ✅ forces JSON output at model level
            options={
                "temperature": 0,   # ✅ deterministic, no creative formatting
                "num_predict": 2048  # ✅ enough tokens for full response
            }
        )

        print("✅ LLM Response received\n")
        return response['message']['content']

    except Exception as e:
        print("❌ LLM ERROR:", e)
        return "{}"