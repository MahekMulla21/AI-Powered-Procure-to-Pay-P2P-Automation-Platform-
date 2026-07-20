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

    try:
        return datetime.strptime(
            str(date_value).strip(),
            "%B %d, %Y"
        ).date()
    except Exception:
        return None


# ─────────────────────────────────────────────
# 🔍 DATA MATCHING LOGIC
# ─────────────────────────────────────────────
def check_existing_record(structured):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        query = """
            SELECT vendor_name, msa_id, start_date,vendor_id
            , end_date, status, created_by, currency, payment_terms
            FROM msa_dataset
            WHERE vendor_name = %s
            AND active_flag = 1
        """

        cursor.execute(query, (structured.get("vendor_name"),))
        records = cursor.fetchall()

        for row in records:
            db_vendor, db_msa_id, db_start_date, db_vendor_id, db_end_date, db_status, db_created_by, db_currency, db_payment = row

            input_vendor = structured.get("vendor_name")
            input_msa_id = structured.get("msa_id")
            input_start_date = format_date(structured.get("start_date"))
            input_vendor_id = structured.get("vendor_id")
            input_end_date = format_date(structured.get("end_date"))
            input_status = structured.get("status")
            input_created_by = structured.get("created_by")
            input_currency = structured.get("currency")
            input_payment = structured.get("payment_terms")

            if (
                db_msa_id     == input_msa_id     and
                db_vendor     == input_vendor     and
                db_vendor_id  == input_vendor_id  and
                db_start_date == input_start_date and
                db_end_date   == input_end_date   and
                db_status     == input_status     and
                db_created_by == input_created_by and
                db_currency   == input_currency   and
                db_payment    == input_payment

            ):
                return "DUPLICATE"

            if db_vendor == input_vendor:
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
            UPDATE msa_dataset
            SET active_flag = 0,
            end_timestamp = %s
            WHERE vendor_name = %s
            AND active_flag = 1
        """

        cursor.execute(query,(datetime.now(), structured.get("vendor_name")))
        conn.commit()

        print("[INFO] Old records deactivated with end_timestamp")

    except Exception as e:
        conn.rollback()
        print("[ERROR] Failed to deactivate old records:", e)

    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# 💾 SAVE TO POSTGRES
# ─────────────────────────────────────────────
def save_to_postgres(structured, file_id=None):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # ✅ Inject file_id into structured
    if file_id is not None:
        structured["file_id"] = file_id

    field_mapping = {
        "msa_id": "msa_id",
        "vendor_name": "vendor_name",
        "vendor_id": "vendor_id",
        "start_date": "start_date",
        "end_date": "end_date",
        "status": "status",
        "created_by": "created_by",
        "currency": "currency",
        "payment_terms": "payment_terms",
        "active_flag": "active_flag",
        "file_id": "file_id",
        "start_timestamp": "start_timestamp",   # ← ADD
        "end_timestamp": "end_timestamp"
    }

    columns = []
    values = []

    for db_column, structured_key in field_mapping.items():
        columns.append(f'"{db_column}"')

        value = structured.get(structured_key)

        # Date conversion
        if db_column in ["start_date", "end_date"]:
            value = format_date(value)

        #timestamp handling for new records
        if db_column == "start_timestamp":
            value = datetime.now()

        if db_column == "end_timestamp":
            value = None # ← Set to None for new records; can be updated later when deactivated

        # Boolean → integer
        if db_column == "active_flag":
            flag = structured.get("active_flag", True)
            value = 1 if flag else 0

        if value == "":
            value = None

        values.append(value)

    query = f"""
        INSERT INTO msa_dataset ({', '.join(columns)})
        VALUES ({', '.join(['%s'] * len(values))})
    """

    try:
        cursor.execute(query, values)
        conn.commit()

        print("[SUCCESS] Structured data saved to PostgreSQL")

    except Exception as e:
        conn.rollback()

        print(f"[ERROR] PostgreSQL Insert Failed: {str(e)}")
        print("[DEBUG] Query:", query)
        print("[DEBUG] Values:", values)

        raise

    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# 📊 SAVE SUMMARY
# ─────────────────────────────────────────────

import logging
logger = logging.getLogger("msa_main")

def save_summary_to_db(summary: list, file_id):
    if not file_id:
        logger.warning("[SUMMARY] No file_id provided — skipping summary DB save")
        return

    if not summary:
        logger.warning("[SUMMARY] Empty summary list — nothing to insert")
        return

    # ✅ Log first row to verify keys before hitting DB
    logger.info("[SUMMARY] Sample row keys: %s", list(summary[0].keys()))
    logger.info("[SUMMARY] Sample row values: %s", summary[0])
    logger.info("[SUMMARY] Total rows to insert: %d", len(summary))

    conn = None
    inserted = 0
    failed = 0

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        for i, row in enumerate(summary):
            try:
                values = (
                    file_id,
                    row.get("document_type", "MSA"),
                    row.get("field_name"),
                    row.get("field_value"),
                    row.get("field_status"),
                    row.get("field_type")
                )

                # ✅ Log each row before insert to catch None/missing values
                logger.debug("[SUMMARY] Row %d | field_name=%s | field_value=%s | status=%s | type=%s",
                    i,
                    row.get("field_name"),
                    row.get("field_value"),
                    row.get("field_status"),
                    row.get("field_type")
                )

                cur.execute("""
                    INSERT INTO extracted_dataset (
                        file_id, document_type, field_name,
                        field_value, field_status, field_type
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, values)

                inserted += 1

            except Exception as row_err:
                # ✅ Log exactly which row failed and why
                logger.error("[SUMMARY] Row %d insert failed | field_name=%s | error=%s",
                    i, row.get("field_name"), row_err)
                failed += 1
                continue   # keep going for remaining rows

        conn.commit()
        cur.close()
        logger.info("[SUMMARY] Done | inserted=%d | failed=%d | file_id=%s",
            inserted, failed, file_id)

    except Exception as e:
        logger.error("[SUMMARY] DB connection/commit failed: %s", e)
        if conn:
            conn.rollback()

    finally:
        if conn:
            conn.close()

# def save_summary_to_db(summary: list, file_id):
#     if not file_id:
#         print("[WARN] No file_id provided — skipping summary DB save")
#         return

#     conn = None

#     try:
#         conn = psycopg2.connect(**DB_CONFIG)
#         cur = conn.cursor()

#         for row in summary:
#             cur.execute("""
#                 INSERT INTO extracted_dataset (
#                     file_id,
#                     document_type,
#                     field_name,
#                     field_value,
#                     field_status,
#                     field_type
#                 )
#                 VALUES (%s, %s, %s, %s, %s, %s)
#             """, (
#                 file_id,
#                 row.get("document_type", "MSA"),
#                 row.get("field_name"),
#                 row.get("field_value"),
#                 row.get("field_status"),
#                 row.get("field_type")
#             ))

#         conn.commit()
#         cur.close()

#         print(f"[DB] Summary saved | file_id={file_id} | {len(summary)} rows inserted")

#     except Exception as e:
#         print(f"[ERROR] Summary DB save failed: {e}")

#         if conn:
#             conn.rollback()

#     finally:
#         if conn:
#             conn.close()