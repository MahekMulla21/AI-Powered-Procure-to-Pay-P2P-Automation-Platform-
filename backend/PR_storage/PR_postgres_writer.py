import json
import psycopg2
from datetime import datetime


DB_CONFIG = {
    "host": "10.1.1.53",
    "database": "clrvw_db",
    "user": "postgres",
    "password": "postgres",
    "port": "5432"
}


# ─────────────────────────────────────────────
# DATE FORMATTER
# ─────────────────────────────────────────────
def format_date(date_value):
    if not date_value:
        return None

    formats = [
        "%B %d, %Y",   # January 01, 2024
        "%d/%m/%Y",    # 01/01/2024
        "%d-%m-%Y",    # 01-01-2024
        "%Y-%m-%d",    # 2024-01-01
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                str(date_value).strip(),
                fmt
            ).date()
        except Exception:
            continue

    return None


# ─────────────────────────────────────────────
# 🔍 DATA MATCHING LOGIC
# ─────────────────────────────────────────────
def check_existing_record(structured):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                pr_id,
                vendor_name,
                requested_by,
                department,
                budget_code,
                priority,
                total_amount,
                currency,
                request_date,
                required_date,
                reference_sow_number,
                reference_msa_number,
                approval_status,
                service_code,
                purchasing_group
            FROM pr_dataset
            WHERE vendor_name = %s
            AND active_flag = 1
        """

        cursor.execute(query, (structured.get("vendor_name"),))
        records = cursor.fetchall()

        for row in records:
            (
                db_pr_id,
                db_vendor_name,
                db_requested_by,
                db_department,
                db_budget_code,
                db_priority,
                db_total_amount,
                db_currency,
                db_request_date,
                db_required_date,
                db_reference_sow_number,
                db_reference_msa_number,
                db_approval_status,
                db_service_code,
                db_purchasing_group
            ) = row

            input_pr_id               = structured.get("pr_id")
            input_vendor_name         = structured.get("vendor_name")
            input_requested_by        = structured.get("requested_by")
            input_department          = structured.get("department")
            input_budget_code         = structured.get("budget_code")
            input_priority            = structured.get("priority")
            input_total_amount        = structured.get("total_amount")
            input_currency            = structured.get("currency")
            input_request_date        = format_date(structured.get("request_date"))
            input_required_date       = format_date(structured.get("required_date"))
            input_reference_sow       = structured.get("reference_sow_number")
            input_reference_msa       = structured.get("reference_msa_number")
            input_approval_status     = structured.get("approval_status")
            input_service_code        = structured.get("service_code")
            input_purchasing_group    = structured.get("purchasing_group")

            # ===============================
            # FULL DUPLICATE CHECK
            # ===============================
            if (
                db_pr_id                == input_pr_id               and
                db_vendor_name          == input_vendor_name         and
                db_requested_by         == input_requested_by        and
                db_department           == input_department          and
                db_budget_code          == input_budget_code         and
                db_priority             == input_priority            and
                db_total_amount         == input_total_amount        and
                db_currency             == input_currency            and
                db_request_date         == input_request_date        and
                db_required_date        == input_required_date       and
                db_reference_sow_number == input_reference_sow       and
                db_reference_msa_number == input_reference_msa       and
                db_approval_status      == input_approval_status     and
                db_service_code         == input_service_code        and
                db_purchasing_group     == input_purchasing_group
            ):
                return "DUPLICATE"

            # ===============================
            # PARTIAL MATCH → REVIEW
            # ===============================
            if db_vendor_name == input_vendor_name:
                return "REVIEW_REQUIRED"

        return "NEW"

    except Exception as e:
        print("[ERROR] Matching failed:", e)
        return "NEW"

    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# 🔥 DEACTIVATE OLD RECORDS
# ─────────────────────────────────────────────
def deactivate_old_records(structured):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        query = """
            UPDATE pr_dataset
            SET active_flag = 0,
                end_timestamp = %s
            WHERE vendor_name = %s
            AND active_flag = 1
        """

        cursor.execute(query, (
            datetime.now(),
            structured.get("vendor_name")
        ))
        conn.commit()

        print("[INFO] Old PR records deactivated with end_timestamp")

    except Exception as e:
        conn.rollback()
        print("[ERROR] Failed to deactivate old PR records:", e)

    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# 💾 SAVE TO POSTGRES
# ─────────────────────────────────────────────
def save_to_postgres(structured, file_id=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Inject file_id into structured
    if file_id is not None:
        structured["file_id"] = file_id

    field_mapping = {
        "pr_id"                 : "pr_id",
        "vendor_name"           : "vendor_name",
        "requested_by"          : "requested_by",
        "department"            : "department",
        "budget_code"           : "budget_code",
        "priority"              : "priority",
        "total_amount"          : "total_amount",
        "currency"              : "currency",
        "request_date"          : "request_date",
        "required_date"         : "required_date",
        "reference_sow_number"  : "reference_sow_number",
        "reference_msa_number"  : "reference_msa_number",
        "approval_status"       : "approval_status",
        "service_code"          : "service_code",
        "purchasing_group"      : "purchasing_group",
        "file_id"               : "file_id",
        "active_flag"           : "active_flag",
        "start_timestamp"       : "start_timestamp",
        "end_timestamp"         : "end_timestamp"
    }

    columns = []
    values = []

    for db_column, structured_key in field_mapping.items():

        columns.append(f'"{db_column}"')

        value = structured.get(structured_key)

        # ===============================
        # DATE CONVERSION
        # ===============================
        if db_column in ["request_date", "required_date"]:
            value = format_date(value)

        # ===============================
        # TIMESTAMP HANDLING
        # ===============================
        if db_column == "start_timestamp":
            value = datetime.now()

        if db_column == "end_timestamp":
            value = None  # Set on deactivation

        # ===============================
        # ACTIVE FLAG
        # ===============================
        if db_column == "active_flag":
            flag = structured.get("active_flag", True)
            value = 1 if flag else 0

        # ===============================
        # EMPTY STRING → NULL
        # ===============================
        if value == "":
            value = None

        values.append(value)

    query = f"""
        INSERT INTO pr_dataset ({', '.join(columns)})
        VALUES ({', '.join(['%s'] * len(values))})
    """

    try:
        cursor.execute(query, values)
        conn.commit()

        print("[SUCCESS] PR structured data saved to PostgreSQL")

    except Exception as e:
        conn.rollback()

        print(f"[ERROR] PostgreSQL Insert Failed: {str(e)}")
        print("[DEBUG] Query  :", query)
        print("[DEBUG] Values :", values)

        raise

    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# 📊 SAVE SUMMARY
# ─────────────────────────────────────────────
def save_summary_to_db(summary: list, file_id: int):
    """
    Save structured field summary rows to extracted_dataset.
    Called after generate_summary() with structured fields only.
    """
    if not file_id:
        print("[WARN] No file_id provided — skipping summary DB save")
        return

    conn = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        for row in summary:
            cur.execute("""
                INSERT INTO extracted_dataset (
                    file_id,
                    document_type,
                    field_name,
                    field_value,
                    field_status,
                    field_type
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                file_id,
                row.get("document_type", "PR"),
                row.get("field_name"),
                row.get("field_values"),        # ← key from generate_summary()
                row.get("field_status"),
                row.get("field_type")
            ))

        conn.commit()
        cur.close()

        print(f"[DB] PR Summary saved | file_id={file_id} | {len(summary)} rows inserted")

    except Exception as e:
        print(f"[ERROR] PR Summary DB save failed: {e}")

        if conn:
            conn.rollback()

    finally:
        if conn:
            conn.close()


# ─────────────────────────────────────────────
# 📦 SAVE UNSTRUCTURED FIELDS TO extracted_dataset
# ─────────────────────────────────────────────
def save_unstructured_to_db(unstructured: dict, file_id: int):
    """
    Save unstructured fields (description, quantity, location)
    to extracted_dataset as individual rows — same format as
    save_summary_to_db so the table stays consistent.

    Each field becomes one row:
        field_name  = "description" / "quantity" / "location"
        field_value = the extracted string value
        field_type  = "unstructured"
        field_status= "extracted" if value present, else "missing"
    """
    if not file_id:
        print("[WARN] No file_id — skipping unstructured DB save")
        return

    if not unstructured:
        print("[WARN] Empty unstructured data — skipping")
        return

    conn = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # ──────────────────────────────────────────
        # Build rows for each unstructured field
        # ──────────────────────────────────────────
        rows_to_insert = []

        # --- description ---
        description = unstructured.get("description")
        rows_to_insert.append({
            "field_name"  : "description",
            "field_value" : str(description).strip() if description else None,
            "field_status": "extracted" if description else "missing",
            "field_type"  : "unstructured"
        })

        # --- quantity (dict → flattened string) ---
        quantity = unstructured.get("quantity")
        if isinstance(quantity, dict):
            quantity_str = ", ".join(
                f"{k}: {v}" for k, v in quantity.items()
            )
        elif quantity:
            quantity_str = str(quantity).strip()
        else:
            quantity_str = None

        rows_to_insert.append({
            "field_name"  : "quantity",
            "field_value" : quantity_str,
            "field_status": "extracted" if quantity_str else "missing",
            "field_type"  : "unstructured"
        })

        # --- location ---
        location = unstructured.get("location")
        rows_to_insert.append({
            "field_name"  : "location",
            "field_value" : str(location).strip() if location else None,
            "field_status": "extracted" if location else "missing",
            "field_type"  : "unstructured"
        })

        # ──────────────────────────────────────────
        # Insert all rows
        # ──────────────────────────────────────────
        for row in rows_to_insert:
            cur.execute("""
                INSERT INTO extracted_dataset (
                    file_id,
                    document_type,
                    field_name,
                    field_value,
                    field_status,
                    field_type
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                file_id,
                "PR",
                row["field_name"],
                row["field_value"],
                row["field_status"],
                row["field_type"]
            ))

        conn.commit()
        cur.close()

        print(
            f"[DB] PR Unstructured saved | "
            f"file_id={file_id} | "
            f"{len(rows_to_insert)} rows inserted"
        )

    except Exception as e:
        print(f"[ERROR] Unstructured DB save failed: {e}")

        if conn:
            conn.rollback()

    finally:
        if conn:
            conn.close()