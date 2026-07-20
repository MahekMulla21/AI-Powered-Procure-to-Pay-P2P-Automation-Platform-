REQUIRED_FIELDS = [
    "vendor_name",
    "vendor_id",
    "start_date",
    "end_date",
    "currency",
    "status",
    "created_by",
    "payment_terms",
    "termination_clause",
    "msa_id"
]

def validate(data):
    structured = data.get("structured", {})

    for field in REQUIRED_FIELDS:
        if field not in structured:
            structured[field] = None

    data["structured"] = structured
    return data