def validate_fields(data):

    results = []

    for field, value in data.items():

        # Default
        status_flag = "Valid"

        # Missing check
        if value == "NA":
            status_flag = "Missing"

        # Special vendor validation
        if field == "vendor_name":
            if value == "NA" or len(value) < 3:
                status_flag = "Missing"

        results.append({
            "field": field,
            "value": value,
            "status": status_flag
        })

    return results