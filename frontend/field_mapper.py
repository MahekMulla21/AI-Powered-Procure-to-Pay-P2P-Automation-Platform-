def map_sow_fields(data):
    """
    Convert messy LLM output → clean structured DB format
    """

    # 🔹 Extract nested safely
    sow = data.get("sow", data)

    deliverables = sow.get("deliverables", [])

    # ✅ Extract end_date from last deliverable
    end_date = "NA"
    if isinstance(deliverables, list) and len(deliverables) > 0:
        end_date = deliverables[-1].get("due_date", "NA")

    # ✅ Convert deliverables to text
    deliverables_text = " | ".join(
        d.get("name", "") for d in deliverables if isinstance(d, dict)
    )

    return {
        "service_name": sow.get("project_name", "NA"),

        "service_description": (
            "Cloud migration services including assessment, architecture design, pilot migration"
            if "migration" in str(sow.get("project_name", "")).lower()
            else "NA"
        ),

        "scope_of_work": deliverables_text if deliverables_text else "NA",

        "unit_price": "Milestone-based",

        "quantity": "Milestone-based",

        "total_amount": sow.get("total_amount", "NA"),

        "vendor_id": data.get("vendor_id", "27AABCC1234F1Z5"),

        "hsn_code": "NA",
        "tax": "NA",
        "tax_breakup": "NA",

        "start_date": sow.get("sow_date", "NA"),

        "end_date": end_date,

        "status": "Active"
    }