import psycopg2
import re
import json
from datetime import datetime


# ============================================================
# DB CONNECTION
# ============================================================

def get_connection():

    return psycopg2.connect(
        host="10.1.1.53",
        database="clrvw_db",
        user="postgres",
        password="postgres",
        port="5432"
    )


# ============================================================
# DATE PARSER
# ============================================================

def parse_date(value):

    if not value:
        return None

    if isinstance(value, datetime):
        return value

    value = str(value).strip()

    formats = [

        "%Y-%m-%d",
        "%B %d, %Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%b %d, %Y"
    ]

    for fmt in formats:

        try:
            return datetime.strptime(value, fmt)

        except Exception:
            continue

    return None


# ============================================================
# NUMERIC CLEANER
# ============================================================

def to_float(value):

    if value is None:
        return None

    try:

        value = (
            str(value)
            .replace(",", "")
            .replace("$", "")
            .replace("₹", "")
            .replace("USD", "")
            .replace("INR", "")
        )

        match = re.search(r"[\d.]+", value)

        return float(match.group()) if match else None

    except Exception:

        return None


# ============================================================
# JSON ARRAY HELPER
# ============================================================

def _to_json_array(value):

    if value is None:
        return None

    if isinstance(value, list):

        if not value:
            return None

        return json.dumps(value)

    return json.dumps([value])


# ============================================================
# REQUIRED AUDIT FIELDS
# ============================================================

SUMMARY_FIELDS = [

    ("po_id", "po_id"),
    ("po_date", "po_date"),
    ("vendor_name", "vendor_name"),
    ("client_name", "client_name"),
    ("payment_terms", "payment_terms"),
    ("delivery_terms", "delivery_terms"),
    ("currency", "currency"),
    ("total_amount", "total_amount"),
    ("start_date", "start_date"),
    ("end_date", "end_date"),
    ("reference_sow", "reference_sow"),
    ("reference_msa", "reference_msa"),
    ("quantity", "quantity"),
    ("unit_price", "unit_price"),
    ("tax", "tax"),
    ("tax_breakup", "tax_breakup"),
    ("service_code", "service_code"),
    ("delivery_location", "delivery_location"),
    ("grn_indicator", "grn_indicator"),
    ("po_status", "po_status")
]


# ============================================================
# ENSURE active_flag EXISTS
# ============================================================

def _ensure_active_flag(cur):

    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'po_dataset'
        AND column_name = 'active_flag'
    """)

    if cur.fetchone() is None:

        cur.execute("""
            ALTER TABLE po_dataset
            ADD COLUMN active_flag INT DEFAULT 1
        """)

        cur.execute("""
            UPDATE po_dataset
            SET active_flag = 1
            WHERE active_flag IS NULL
        """)

        print("[MIGRATION] active_flag added")


# ============================================================
# CHECK EXISTING ACTIVE RECORD
# ============================================================

def check_existing_record(cur, po_id):

    cur.execute(
        """
        SELECT COUNT(*)
        FROM po_dataset
        WHERE po_id = %s
        AND active_flag = 1
        """,
        (po_id,)
    )

    return cur.fetchone()[0] > 0


# ============================================================
# FETCH ACTIVE RECORD
# ============================================================

def fetch_active_po(cur, po_id):

    cur.execute(
        """
        SELECT *
        FROM po_dataset
        WHERE po_id = %s
        AND active_flag = 1
        LIMIT 1
        """,
        (po_id,)
    )

    row = cur.fetchone()

    if not row:
        return None

    columns = [desc[0] for desc in cur.description]

    return dict(zip(columns, row))


# ============================================================
# DUPLICATE CHECK
# ============================================================

def is_duplicate(cur, po_id, new_data):

    cur.execute(
        """
        SELECT vendor_name,
               total_amount,
               reference_sow,
               reference_msa
        FROM po_dataset
        WHERE po_id = %s
        AND active_flag = 1
        LIMIT 1
        """,
        (po_id,)
    )

    row = cur.fetchone()

    if not row:
        return False

    db_data = {

        "vendor_name": str(row[0] or "").strip().lower(),
        "total_amount": str(row[1] or "").strip(),
        "reference_sow": str(row[2] or "").strip().lower(),
        "reference_msa": str(row[3] or "").strip().lower()
    }

    new_norm = {

        "vendor_name": str(
            new_data.get("vendor_name") or ""
        ).strip().lower(),

        "total_amount": str(
            new_data.get("total_amount") or ""
        ).strip(),

        "reference_sow": str(
            new_data.get("reference_sow") or ""
        ).strip().lower(),

        "reference_msa": str(
            new_data.get("reference_msa") or ""
        ).strip().lower()
    }

    return db_data == new_norm


# ============================================================
# DEACTIVATE OLD RECORDS
# ============================================================

def deactivate_old_po(cur, po_id):

    cur.execute(
        """
        UPDATE po_dataset
        SET active_flag = 0
        WHERE po_id = %s
        AND active_flag = 1
        """,
        (po_id,)
    )

    print(f"[DEACTIVATE] po_id={po_id}")


# ============================================================
# INSERT INTO po_dataset
# ============================================================

def insert_po(
    cur,
    data,
    active_flag=1,
    file_id=None
):

    query = """
        INSERT INTO po_dataset (

            po_id,
            po_date,
            vendor_name,
            client_name,
            payment_terms,
            delivery_terms,
            currency,
            total_amount,
            start_date,
            end_date,
            reference_sow,
            reference_msa,
            quantity,
            unit_price,
            tax,
            tax_breakup,
            service_code,
            delivery_location,
            grn_indicator,
            po_status,
            active_flag,
            file_id

        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s::jsonb,
            %s::jsonb,
            %s::jsonb,
            %s,
            %s::jsonb,
            %s,
            %s,
            %s,
            %s,
            %s
        )
    """

    currency_str = str(data.get("currency", ""))

    if "(" in currency_str:
        currency_code = currency_str.split("(")[0].strip()
    else:
        currency_code = currency_str[:3]

    currency_code = currency_code[:10]

    values = (

        str(data.get("po_id", ""))[:50],
        data.get("po_date"),
        data.get("vendor_name"),
        data.get("client_name"),
        data.get("payment_terms"),
        data.get("delivery_terms"),
        currency_code,
        data.get("total_amount"),
        data.get("start_date"),
        data.get("end_date"),
        str(data.get("reference_sow", ""))[:50],
        str(data.get("reference_msa", ""))[:50],

        _to_json_array(data.get("quantity")),
        _to_json_array(data.get("unit_price")),
        _to_json_array(data.get("tax")),

        json.dumps(data.get("tax_breakup"))
        if data.get("tax_breakup") is not None
        else None,

        _to_json_array(data.get("service_code")),

        data.get("delivery_location"),

        True
        if data.get("grn_indicator")
        and "required" in str(data.get("grn_indicator")).lower()
        else False,

        str(data.get("po_status", ""))[:50],

        active_flag,
        file_id
    )

    cur.execute(query, values)

    print("[INSERT] po_dataset saved")


# ============================================================
# SAVE TO extracted_dataset
# ============================================================

def save_summary_to_db(
    cur,
    conn,
    structured,
    unstructured,
    file_id
):

    query = """
        INSERT INTO extracted_dataset
        (
            file_id,
            document_type,
            field_name,
            field_value,
            field_status,
            field_type
        )
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    print(f"[extracted_dataset] Starting save for file_id={file_id}")

    # ============================================================
    # STRUCTURED FIELDS
    # ============================================================

    structured_count = 0

    for field_name, data_key in SUMMARY_FIELDS:

        value = structured.get(data_key)

        if isinstance(value, list):

            field_value = json.dumps(value)

            field_status = (
                "Valid"
                if value else "Missing"
            )

        else:

            if (
                value is None
                or str(value).strip() == ""
            ):

                field_value = "NA"
                field_status = "Missing"

            else:

                field_value = str(value).strip()
                field_status = "Valid"

        cur.execute(
            query,
            (
                file_id,
                "PO",
                field_name,
                field_value,
                field_status,
                "structured"
            )
        )

        structured_count += 1

    print(
        f"[extracted_dataset] "
        f"{structured_count} structured rows inserted"
    )

    conn.commit()

    # ============================================================
    # UNSTRUCTURED FIELDS
    # ============================================================

    if unstructured:

        unstructured_count = 0

        for field_name, value in unstructured.items():

            if (
                value is None
                or str(value).strip() == ""
            ):

                field_value = "NA"
                field_status = "Missing"

            else:

                field_value = str(value).strip()
                field_status = "Valid"

            cur.execute(
                query,
                (
                    file_id,
                    "PO",
                    field_name,
                    field_value,
                    field_status,
                    "unstructured"
                )
            )

            unstructured_count += 1

        conn.commit()

        print(
            f"[extracted_dataset] "
            f"{unstructured_count} unstructured rows inserted"
        )

    else:

        print("[extracted_dataset] No unstructured data")

    cur.execute(
        "SELECT COUNT(*) FROM extracted_dataset WHERE file_id = %s",
        (file_id,)
    )

    count = cur.fetchone()[0]

    print(
        f"[extracted_dataset] "
        f"VERIFICATION: {count} rows found"
    )


# ============================================================
# MAIN SAVE FUNCTION
# ============================================================

def save_to_postgres(
    structured,
    unstructured=None,
    file_id=None,
    pre_status=None
):

    conn = None
    cur = None

    try:

        print("\n[DB] Connecting...")

        po_id = structured.get("po_id")

        if not po_id:

            import uuid

            po_id = f"PO-AUTO-{str(uuid.uuid4())[:8]}"

            structured["po_id"] = po_id

            print(f"[WARN] Generated po_id={po_id}")

        conn = get_connection()

        cur = conn.cursor()

        _ensure_active_flag(cur)

        conn.commit()

        save_summary_to_db(
            cur,
            conn,
            structured,
            unstructured,
            file_id
        )

        exists = check_existing_record(
            cur,
            po_id
        )

        if pre_status is None:

            if exists:

                duplicate = is_duplicate(
                    cur,
                    po_id,
                    structured
                )

                pre_status = (
                    "DUPLICATE"
                    if duplicate
                    else "REVIEW_REQUIRED"
                )

            else:

                pre_status = "NEW"

        print(f"[DB] STATUS = {pre_status}")

        if pre_status == "DUPLICATE":

            conn.commit()

            print("[DUPLICATE] skipped")

            return {
                "action": "DUPLICATE",
                "po_id": po_id
            }

        elif pre_status == "REVIEW_REQUIRED":

            deactivate_old_po(
                cur,
                po_id
            )

            insert_po(
                cur,
                structured,
                active_flag=1,
                file_id=file_id
            )

            conn.commit()

            print("[UPDATE] New version inserted")

            return {
                "action": "UPDATE",
                "po_id": po_id
            }

        else:

            insert_po(
                cur,
                structured,
                active_flag=1,
                file_id=file_id
            )

            conn.commit()

            print("[NEW] Inserted")

            return {
                "action": "NEW",
                "po_id": po_id
            }

    except Exception as e:

        import traceback

        print("\n[DB ERROR]")

        traceback.print_exc()

        if conn:
            conn.rollback()

        raise e

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()

        print("[DB] Connection closed")