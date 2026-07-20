import json
import pandas as pd


def generate_summary(data, document_type="PR"):
    summary = []

    structured = data.get("structured", {})
    unstructured = data.get("unstructured", {})

    # ===============================
    # STRUCTURED FIELDS
    # ===============================
    STRUCTURED_FIELDS = [
        "pr_id",
        "request_date",
        "requested_by",
        "department",
        "vendor_name",
        "budget_code",
        "priority",
        "total_amount",
        "currency",
        "required_date",
        "reference_sow_number",
        "reference_msa_number",
        "approval_status",
        "service_code",
        "purchasing_group"
    ]

    for field in STRUCTURED_FIELDS:

        value = structured.get(field, None)

        if value is None or str(value).strip() == "" or str(value).strip().lower() == "na":
            status = "Missing"
            value = "NA"
        else:
            status = "Valid"

        summary.append({
            "document_type": document_type,
            "field_name": field,
            "field_values": value,
            "field_status": status,
            "field_type": "structured"
        })

    # ===============================
    # UNSTRUCTURED FIELDS
    # ===============================
    UNSTRUCTURED_FIELDS = [
        "quantity",
        "location",
        "description"
    ]

    for field in UNSTRUCTURED_FIELDS:

        value = unstructured.get(field, None)

        # quantity is JSONB — serialize for summary
        if field == "quantity":

            if isinstance(value, dict):

                if value:
                    value = json.dumps(value)
                    status = "Valid"
                else:
                    value = "NA"
                    status = "Missing"

            elif value is None or str(value).strip() == "":
                value = "NA"
                status = "Missing"

            else:
                status = "Valid"

        else:

            if value is None or str(value).strip() == "":
                value = "NA"
                status = "Missing"
            else:
                status = "Valid"

        summary.append({
            "document_type": document_type,
            "field_name": field,
            "field_values": value,
            "field_status": status,
            "field_type": "unstructured"
        })

    return summary


def save_summary(summary, path="data/output/PR_summary.xlsx"):
    df = pd.DataFrame(summary)
    df.to_excel(path, index=False)