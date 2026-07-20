REQUIRED_FIELDS = [
  "invoice_number",
    "vendor_name",
    "client_name",
    "invoice_date",
    "due_date",
    "po_reference_number",
    "grn_reference",
    "hsn_code",
    "quantity",
    "unit_price",
    "total_amount",
    "tax",
    "currency",
    "company_code",
    "status"
]

def validate(data):
    structured = data.get("structured", {})

    for field in REQUIRED_FIELDS:
        if field not in structured:
            structured[field] = None

    data["structured"] = structured
    return data