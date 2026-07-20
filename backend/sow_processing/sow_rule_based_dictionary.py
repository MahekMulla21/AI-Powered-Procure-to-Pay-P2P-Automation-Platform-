"""
SOW Rule-Based Dictionary
=========================
Single source of truth for ALL extraction rules — both structured and
unstructured fields. No regex anywhere in this file.
"""

# ═══════════════════════════════════════════════════════════════════════════════
#  GLOBAL NOISE
# ═══════════════════════════════════════════════════════════════════════════════

GLOBAL_NOISE_PREFIXES: list[str] = [
    "confidential",
    "statement of work |",
    "statement of work|",
    "statementofwork |",
    "statementofwork|",
    "page ",
    "proprietary",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  DATE RESOLUTION DICTIONARY
# ═══════════════════════════════════════════════════════════════════════════════

MONTH_NAMES: dict[str, str] = {
    "january": "01", "february": "02", "march": "03",    "april": "04",
    "may":     "05", "june":     "06", "july":  "07",    "august": "08",
    "september":"09","october": "10",  "november":"11",  "december":"12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}

# ═══════════════════════════════════════════════════════════════════════════════
#  CURRENCY DETECTION DICTIONARY
# ═══════════════════════════════════════════════════════════════════════════════

CURRENCY_KEYWORDS: dict[str, str] = {
    "usd":                   "USD",
    "united states dollar":  "USD",
    "usd(unitedstatesdollar)": "USD",
    "inr":                   "INR",
    "indian rupee":          "INR",
    "eur":                   "EUR",
    "euro":                  "EUR",
    "gbp":                   "GBP",
    "pound":                 "GBP",
    "sar":                   "SAR",
    "saudi riyal":           "SAR",
    "aed":                   "AED",
    "sgd":                   "SGD",
}

CURRENCY_SYMBOLS: dict[str, str] = {
    "$":  "USD",
    "₹":  "INR",
    "€":  "EUR",
    "£":  "GBP",
}

# ═══════════════════════════════════════════════════════════════════════════════
#  STRUCTURED FIELD DICTIONARY
# ═══════════════════════════════════════════════════════════════════════════════

STRUCTURED_FIELD_DICTIONARY: dict[str, dict] = {

    "sow_id": {
        "labels": [
            "SOW ID",
            "SOWID",
            "SOW No",
            "SOWNo",
            "SOW Number",
            "SOWNumber",
            "Statement of Work ID",
            "SOW Reference",
            "SOWReference",
            "SOW Ref",
            "SOWRef",
        ],
        "value_type": "text",
        "fallback_scan": ["SOW-TCS", "SOW-STC", "SOW-DM"],
    },

    "reference_msa": {
        "labels": [
            "MSA Reference",
            "MSAReference",
            "MSA Ref",
            "MSARef",
            "MSA ID",
            "MSAID",
            "MSA Number",
            "MSANumber",
            "Master Service Agreement",
            "Reference MSA",
            "MSA No",
            "MSANo",
        ],
        "value_type": "text",
        "fallback_scan": ["MSA-TCS", "MSA-STC"],
    },

    "vendor_id": {
        "labels": [
            "Vendor ID",
            "VendorID",
            "Vendor Code",
            "VendorCode",
            "Vendor No",
            "VendorNo",
            "Supplier ID",
            "SupplierID",
            "Service Provider ID",
        ],
        "value_type": "text",
        "fallback_scan": ["VND-"],
    },

    "vendor_name": {
        "labels": [
            "Vendor Name",
            "VendorName",
            "Vendor / Service Provider",
            "Vendor/Service Provider",
            "VENDOR / SERVICE PROVIDER",
            "VENDOR/SERVICEPROVIDER",
            "Service Provider",
            "ServiceProvider",
            "Supplier Name",
            "SupplierName",
            "Contractor Name",
            "ContractorName",
        ],
        "value_type": "text",
        "fallback_scan": [],
    },

    "client_name": {
        "labels": [
            "Client Name",
            "ClientName",
            "Client",
            "Customer Name",
            "CustomerName",
            "Buyer",
            "Customer",
        ],
        "value_type": "text",
        "fallback_scan": [],
    },

    "project_title": {
        "labels": [
            "Project Title",
            "ProjectTitle",
            "Project Name",
            "ProjectName",
            "Engagement Name",
            "EngagementName",
            "SOW Title",
            "SOWTitle",
            "Project",
        ],
        "value_type": "text",
        "fallback_scan": [],
    },

    "start_date": {
        "labels": [
            "SOW Start Date",
            "SOWStartDate",
            "Start Date",
            "StartDate",
            "Effective Date",
            "EffectiveDate",
            "Commencement Date",
            "CommencementDate",
            "Project Start Date",
            "ProjectStartDate",
            "SOW Effective Date",
            "SOWEffectiveDate",
            "Date",
        ],
        "value_type": "date",
        "fallback_scan": [],
    },

    "end_date": {
        "labels": [
            "SOW End Date",
            "SOWEndDate",
            "End Date",
            "EndDate",
            "Completion Date",
            "CompletionDate",
            "Expiry Date",
            "ExpiryDate",
            "Project End Date",
            "ProjectEndDate",
            "Termination Date",
            "TerminationDate",
            "SOW Expiry Date",
            "SOWExpiryDate",
        ],
        "value_type": "date",
        "fallback_scan": [],
    },

    "payment_terms": {
        "labels": [
            "Payment Terms",
            "PaymentTerms",
            "Payment Term",
            "PaymentTerm",
            "Terms of Payment",
            "Billing Terms",
            "BillingTerms",
            "Invoice Terms",
            "InvoiceTerms",
            "Schedule Type",
        ],
        "value_type": "text",
        "fallback_scan": [],
    },

    "currency": {
        "labels": [
            "Currency",
            "Billing Currency",
            "BillingCurrency",
            "Invoice Currency",
            "InvoiceCurrency",
            "Contract Currency",
            "ContractCurrency",
        ],
        "value_type": "currency_code",
        "fallback_scan": ["USD", "INR", "EUR", "GBP", "SAR"],
    },

    "status": {
        "labels": [
            "Status",
            "Project Status",
            "ProjectStatus",
            "SOW Status",
            "SOWStatus",
            "Contract Status",
            "ContractStatus",
            "Engagement Status",
            "EngagementStatus",
        ],
        "value_type": "text",
        "fallback_scan": ["Active", "Inactive", "Draft", "Closed",
                          "Expired", "Terminated", "On Hold",
                          "In Progress", "Completed", "Pending"],
    },

    "total_amount": {
        "labels": [
            "TOTAL",
            "Total Amount",
            "TotalAmount",
            "Total Cost",
            "TotalCost",
            "Grand Total",
            "GrandTotal",
            "Total Contract Value",
            "Contract Value",
            "Total Value",
            "Total Fee",
        ],
        "value_type": "amount",
        "fallback_scan": [],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
#  UNSTRUCTURED FIELD DICTIONARY
# ═══════════════════════════════════════════════════════════════════════════════

UNSTRUCTURED_FIELD_DICTIONARY: dict[str, dict] = {

    "service_description": {
        "anchors": [
            "2. project background & objectives",
            "2. project background and objectives",
            "project background & objectives",
            "project background and objectives",
            "project background",
            "background & objectives",
            "background and objectives",
            "overview",
            "project overview",
            "purpose",
            "introduction",
        ],
        "stops": [
            "3. scope",
            "scope of services",
            "scope of work",
            "deliverables",
            "milestones",
            "assumptions",
            "intellectual property",
            "payment",
        ],
        "max_lines": 10,
        "min_line_len": 20,
        "skip_prefixes": GLOBAL_NOISE_PREFIXES,
        "post_process": "join_paragraphs",
    },

    "scope_of_work": {
        "anchors": [
            "3.1 in-scope services",
            "in-scope services",
            "in scope services",
            "3. scope of services",
            "scope of services",
            "scope of work",
            "3. scope",
            "services",
        ],
        "stops": [
            "3.2 out-of-scope",
            "3.2 out of scope",
            "out-of-scope",
            "out of scope",
            "4. deliverables",
            "deliverables",
            "milestones",
            "assumptions",
        ],
        "max_lines": 80,
        "min_line_len": 0,
        "skip_prefixes": GLOBAL_NOISE_PREFIXES,
        "post_process": "format_phases",
        "phase_keywords": [
            "phase 1", "phase 2", "phase 3", "phase 4", "phase 5",
            "phase 6", "phase i", "phase ii", "phase iii", "phase iv",
            "phase v",
        ],
        "bullet_chars": ["•", "-", "–", "*"],
        "max_bullets_per_phase": 3,
    },

    "deliverables": {
        "anchors": [
            "4. deliverables",
            "deliverables",
        ],
        "stops": [
            "5. milestones",
            "milestones & payment",
            "milestones and payment",
            "payment schedule",
            "assumptions",
            "6.",
        ],
        "max_lines": 20,
        "min_line_len": 0,
        "skip_prefixes": GLOBAL_NOISE_PREFIXES,
        "post_process": "extract_deliverable_items",
        "deliverable_codes": ["D1", "D2", "D3", "D4", "D5",
                              "D6", "D7", "D8", "D9", "D10"],
        "bullet_chars": ["•", "-", "–", "*"],
    },

    "payment_schedule": {
        "anchors": [
            "5. milestones & payment schedule",
            "5. milestones and payment schedule",
            "milestones & payment schedule",
            "milestones and payment schedule",
            "5. milestones",
            "payment schedule",
            "payment milestones",
            "milestone payment",
        ],
        "stops": [
            "6. assumptions",
            "6.",
            "assumptions & dependencies",
            "assumptions and dependencies",
            "intellectual property",
            "confidentiality",
        ],
        "max_lines": 30,
        "min_line_len": 0,
        "skip_prefixes": GLOBAL_NOISE_PREFIXES,
        "post_process": "extract_milestone_rows",
        "milestone_prefixes": [
            "M1", "M2", "M3", "M4", "M5", "M6", "M7",
            "Milestone", "TOTAL", "Total",
        ],
    },

    "resource_requirements": {
        "anchors": [
            "15. project team & key contacts",
            "15. project team and key contacts",
            "project team & key contacts",
            "project team and key contacts",
            "15. project team",
            "project team",
            "key contacts",
            "resource requirements",
            "team structure",
            "team composition",
        ],
        "stops": [
            "16. change management",
            "change management",
            "authorized signatures",
            "governing law",
            "17.",
        ],
        "max_lines": 20,
        "min_line_len": 4,
        "skip_prefixes": GLOBAL_NOISE_PREFIXES + [
            "role",
            "name",
            "organization",
            "responsibility",
            "the following personnel",
        ],
        "post_process": "bullet_lines",
    },

    "acceptance_criteria": {
        "anchors": [
            "acceptance criteria",
            "acceptance conditions",
            "acceptance and review",
            "review and acceptance",
        ],
        "stops": [
            "indemnification",
            "liability",
            "governing law",
            "termination",
            "signatures",
            "dispute",
        ],
        "max_lines": 15,
        "min_line_len": 0,
        "skip_prefixes": GLOBAL_NOISE_PREFIXES,
        "post_process": "plain",
        "fact_markers": [
            "business days of submission",
            "written acceptance",
            "sharepoint",
            "docx, pdf",
            "ten (10) business days",
            "acceptance within",
            "submitted in english",
        ],
    },

    "termination_clause": {
        "anchors": [
            "13. termination clause",
            "13. termination",
            "termination clause",
        ],
        "stops": [
            "14. governing law",
            "14.",
            "governing law",
            "15. project team",
            "authorized signatures",
        ],
        "max_lines": 15,
        "min_line_len": 10,
        "skip_prefixes": GLOBAL_NOISE_PREFIXES,
        "post_process": "plain",
    },
}