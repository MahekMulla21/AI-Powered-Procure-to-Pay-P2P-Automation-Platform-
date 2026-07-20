STRUCTURED_FIELDS = [
    "sow_id", "reference_msa", "vendor_id", "vendor_name",
    "client_name", "project_title", "start_date", "end_date",
    "payment_terms", "currency", "status", "total_amount",
]

UNSTRUCTURED_FIELDS = [
    "service_description",
    "scope_of_work",
    "deliverables",
    "payment_schedule",
    "resource_requirements",
    "acceptance_criteria",
    "termination_clause",
]

ALL_FIELDS = STRUCTURED_FIELDS + UNSTRUCTURED_FIELDS

FIELD_PATTERNS = {
    "sow_id": [
        "sow id", "sow_id", "sow no", "sow number",
        "statement of work id",
    ],
    "reference_msa": [
        "msa reference", "msa ref", "msa id", "msa number",
        "master service agreement", "reference msa",
    ],
    "vendor_id": [
        "vendor id", "vendor_id", "vendor code", "vendor no",
    ],
    "vendor_name": [
        "vendor name", "service provider", "supplier name",
        "contractor name",
    ],
    "client_name": [
        "client name", "client", "customer name", "buyer",
    ],
    "project_title": [
        "project title", "project name", "engagement name",
        "sow title",
    ],
    "start_date": [
        "sow start date", "start date", "effective date",
        "commencement date", "project start date",
    ],
    "end_date": [
        "sow end date", "end date", "completion date",
        "expiry date", "project end date",
    ],
    "payment_terms": [
        "payment terms", "payment term", "terms of payment",
        "billing terms",
    ],
    "currency": [
        "currency",
    ],
    "status": [
        "status", "project status", "sow status",
    ],
    "total_amount": [
        "total", "total amount", "total cost", "grand total",
        "total contract value", "contract value",
    ],
}
