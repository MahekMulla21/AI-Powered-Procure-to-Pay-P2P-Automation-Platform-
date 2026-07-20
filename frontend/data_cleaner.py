# data_cleaner.py
import json


def clean_llm_output(raw_text: str) -> dict:
    if not raw_text:
        return {}

    text = raw_text.strip()

    # remove markdown if present
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    # find JSON block
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        print("❌ No JSON found")
        return {}

    json_text = text[start:end+1]

    try:
        data = json.loads(json_text)
    except Exception as e:
        print("❌ JSON Parse Error:", e)
        print("RAW:", raw_text)
        return {}

    # normalize values
    cleaned = {}
    for k, v in data.items():
        if v is None or str(v).strip() == "":
            cleaned[k] = "NA"
        else:
            cleaned[k] = v

    return cleaned