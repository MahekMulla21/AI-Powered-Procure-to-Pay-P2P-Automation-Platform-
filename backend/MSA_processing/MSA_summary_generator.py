import pandas as pd

def generate_summary(data, document_type="MSA"):
    summary = []

    structured = data.get("structured", {})
    unstructured = data.get("unstructured", {})

    # ===============================
    # STRUCTURED FIELDS
    # ===============================
    for field, value in structured.items():

        if value is None or str(value).strip() == "" or str(value).strip().lower() == "na":
            status = "Missing"
            value = "NA"
        else:
            status = "Valid"

        summary.append({
            "document_type": document_type,
            "field_name": field,
            "field_value": value,
            "field_status": status,
            "field_type": "structured"
        })

    # ===============================
    # UNSTRUCTURED FIELDS (🔥 ADD THIS)
    # ===============================
    for field, value in unstructured.items():

        if value is None or str(value).strip() == "":
            status = "Missing"
            value = "NA"
        else:
            status = "Valid"

        summary.append({
            "document_type": document_type,
            "field_name": field,
            "field_value": value,
            "field_status": status,
            "field_type": "unstructured"
        })

    return summary


def save_summary(summary, path="data/output/summary.xlsx"):
    df = pd.DataFrame(summary)
    df.to_excel(path, index=False)