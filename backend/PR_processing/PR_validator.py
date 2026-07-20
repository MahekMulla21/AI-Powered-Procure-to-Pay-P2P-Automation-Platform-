# ===============================
# REQUIRED STRUCTURED FIELDS
# ===============================
REQUIRED_STRUCTURED_FIELDS = [
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

# ===============================
# REQUIRED UNSTRUCTURED FIELDS
# ===============================
REQUIRED_UNSTRUCTURED_FIELDS = [
    "quantity",
    "location",
    "description"
]


def validate(data):

    structured = data.get("structured", {})
    unstructured = data.get("unstructured", {})

    # ===============================
    # VALIDATE STRUCTURED FIELDS
    # ===============================
    for field in REQUIRED_STRUCTURED_FIELDS:

        if field not in structured:
            structured[field] = None

    # ===============================
    # VALIDATE UNSTRUCTURED FIELDS
    # ===============================
    for field in REQUIRED_UNSTRUCTURED_FIELDS:

        if field not in unstructured:

            # quantity defaults to empty dict (JSONB)
            if field == "quantity":
                unstructured[field] = {}
            else:
                unstructured[field] = None

    data["structured"] = structured
    data["unstructured"] = unstructured

    return data