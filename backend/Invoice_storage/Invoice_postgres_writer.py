"""
Invoice_postgres_writer.py
==========================
All PostgreSQL write operations for the Invoice pipeline.

Bug fixed (save_summary_to_db):
  The INSERT into files_dataset had 4 %s placeholders but only 3 values.
  The field_name column was accidentally deleted from both the column list
  and the values tuple, but the 4th %s remained → psycopg2 raised
  'tuple index out of range'. Fixed: field_name is now back in both.
"""

import logging
import re
import psycopg2
import json
from datetime import datetime

logger = logging.getLogger("Invoice_postgres_writer")

DB_CONFIG = {
    "host":     "10.1.1.53",
    "database": "clrvw_db",
    "user":     "postgres",
    "password": "postgres",
    "port":     "5432",
}


# ─────────────────────────────────────────────
# DATE FORMATTER
# ─────────────────────────────────────────────
def format_date(date_value):
    if not date_value:
        return None

    formats = [
        "%B %d, %Y",   # January 15, 2024
        "%d/%m/%Y",    # 15/01/2024
        "%m-%d-%Y",    # 01-15-2024
        "%Y-%m-%d",    # 2024-01-15
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(date_value).strip(), fmt).date()
        except Exception:
            continue

    return None


# ─────────────────────────────────────────────
# NUMERIC CLEANER
# Strips currency symbols (USD), text (LS), commas
# Returns float or None
# ─────────────────────────────────────────────
def clean_numeric(val):
    if val is None or str(val).strip() == "":
        return None
    cleaned = re.sub(r"[^\d.]", "", str(val))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


# ─────────────────────────────────────────────
# 🔍 DATA MATCHING LOGIC
# ─────────────────────────────────────────────
def _get_connection(context: str = ""):
    """Open a psycopg2 connection with structured error logging."""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as exc:
        logger.error(
            "[DB] Connection failed | context=%s | host=%s | db=%s | error=%s",
            context, DB_CONFIG["host"], DB_CONFIG["database"], exc,
        )
        raise


def check_existing_record(structured):
    conn = _get_connection("check_existing_record")
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                invoice_number,
                vendor_name,
                invoice_date,
                due_date,
                po_reference_number,
                grn_reference,
                msa_reference,
                sow_reference,
                total_amount,
                tax,
                currency,
                status
            FROM invoice_dataset
            WHERE invoice_number = %s
        """

        cursor.execute(query, (structured.get("invoice_number"),))
        records = cursor.fetchall()

        for row in records:
            (
                db_invoice_number,
                db_vendor_name,
                db_invoice_date,
                db_due_date,
                db_po_reference_number,
                db_grn_reference,
                db_msa_reference,
                db_sow_reference,
                db_total_amount,
                db_tax,
                db_currency,
                db_status
            ) = row

            # ── Input values ──────────────────────────────
            input_invoice_number = structured.get("invoice_number")
            input_invoice_date   = format_date(structured.get("invoice_date"))
            input_due_date       = format_date(structured.get("due_date"))
            input_po_reference   = structured.get("po_reference_number")
            input_total_amount   = clean_numeric(structured.get("total_amount"))
            input_tax            = clean_numeric(structured.get("tax"))
            input_currency       = structured.get("currency")
            input_status         = structured.get("status")

            # ── Full match → DUPLICATE (key financial fields must match) ─────────────
            if (
                db_invoice_number      == input_invoice_number  and
                db_invoice_date        == input_invoice_date    and
                db_due_date            == input_due_date        and
                db_po_reference_number == input_po_reference    and
                db_total_amount        == input_total_amount    and
                db_tax                 == input_tax             and
                db_currency            == input_currency        and
                db_status              == input_status
            ):
                return "DUPLICATE"

            # ── Same invoice number, different content → REVIEW ──
            if db_invoice_number == input_invoice_number:
                return "REVIEW_REQUIRED"

        return "NEW"

    except Exception as e:
        logger.error("[DB] check_existing_record failed: %s", e)
        return "NEW"

    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# 🔥 DEACTIVATE OLD RECORDS
# ─────────────────────────────────────────────
def deactivate_old_records(structured):
    conn = _get_connection("deactivate_old_records")
    cursor = conn.cursor()

    try:
        query = """
            UPDATE invoice_dataset
            SET active_flag = 0
            WHERE invoice_number = %s
        """

        cursor.execute(query, (structured.get("invoice_number"),))
        conn.commit()

        print(f"[INFO] Old records deactivated for invoice_number={structured.get('invoice_number')}")

    except Exception as e:
        conn.rollback()
        print("[ERROR] Failed to deactivate old records:", e)

    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# 💾 SAVE TO POSTGRES
# ─────────────────────────────────────────────
def save_to_postgres(structured, file_id=None, unstructured=None):
    conn = _get_connection("save_to_postgres")
    cursor = conn.cursor()

    if file_id is not None:
        structured["file_id"] = file_id

    if unstructured is None:
        unstructured = {}

    field_mapping = {
        # ── Primary identifier ──────────────────────────────────────────────────────────
        "invoice_number":      "invoice_number",   # TEXT column
        "invoice_id":          "invoice_number",   # VARCHAR(50) col — same value
        # ── Core fields ───────────────────────────────────────────────────────────────
        "vendor_name":         "vendor_name",
        "client_name":         "client_name",
        "invoice_date":        "invoice_date",
        "due_date":            "due_date",
        "po_reference_number": "po_reference_number",
        "grn_reference":       "grn_reference",
        # ── Cross-reference IDs (DB columns differ from extractor key names) ─────────
        "msa_reference":       "msa_id",           # DB: msa_reference ← extracted: msa_id
        "sow_reference":       "sow_id",           # DB: sow_reference ← extracted: sow_id
        # ── Line item fields ────────────────────────────────────────────────────────────
        "hsn_code":            "hsn_code",
        "quantity":            "quantity",
        "unit_price":          "unit_price",
        "total_amount":        "total_amount",
        "tax":                 "tax",
        "currency":            "currency",
        "company_code":        "company_code",
        "status":              "status",
        # ── Unstructured / JSONB columns ─────────────────────────────────────────────
        "tax_breakup":         "__unstructured__.tax_breakup",
        "bank_details":        "__unstructured__.bank_details",
        "description_of_service": "__unstructured__.description_of_service",
        # ── Meta columns ─────────────────────────────────────────────────────────────
        "active_flag":         "active_flag",
        "file_id":             "file_id",
    }

    # JSONB columns — serialised to JSON string
    JSONB_COLUMNS = {"tax_breakup", "bank_details", "description_of_service"}

    # Numeric columns that need cleaning
    NUMERIC_COLUMNS = {"quantity", "unit_price", "total_amount", "tax"}

    columns = []
    values  = []

    for db_column, structured_key in field_mapping.items():
        columns.append(f'"{db_column}"')

        # Unstructured fields use a special lookup path: "__unstructured__.field"
        if structured_key.startswith("__unstructured__."):
            field = structured_key.split(".", 1)[1]
            value = unstructured.get(field)
        else:
            value = structured.get(structured_key)

        # Date conversion
        if db_column in ["invoice_date", "due_date"]:
            value = format_date(value)

        # JSONB serialization — store as JSON string
        elif db_column in JSONB_COLUMNS:
            if value is not None:
                value = json.dumps({"value": value}) if not isinstance(value, (dict, list)) else json.dumps(value)
            # None stays None (NULL in DB)

        # Numeric cleaning — strips "USD", "LS", commas, etc.
        elif db_column in NUMERIC_COLUMNS:
            value = clean_numeric(value)

        # Boolean → integer
        elif db_column == "active_flag":
            value = 1 if structured.get("active_flag", True) else 0

        # Empty string → NULL
        if value == "":
            value = None

        values.append(value)

    query = f"""
        INSERT INTO invoice_dataset ({', '.join(columns)})
        VALUES ({', '.join(['%s'] * len(values))})
    """

    try:
        # Pre-flight: assert column and value counts match
        assert len(columns) == len(values), (
            f"[DB] Column/value count mismatch: {len(columns)} columns vs {len(values)} values"
        )
        logger.debug(
            "[DB] save_to_postgres | columns=%d | values=%d | file_id=%s",
            len(columns), len(values), file_id,
        )
        cursor.execute(query, values)
        conn.commit()
        logger.info(
            "[DB] Structured data saved → invoice_dataset | file_id=%s", file_id
        )

    except Exception as e:
        conn.rollback()
        logger.error(
            "[DB] save_to_postgres failed | file_id=%s | error=%s\n  query=%s\n  values=%s",
            file_id, e, query, values,
        )
        raise

    finally:
        cursor.close()
        conn.close()



# ─────────────────────────────────────────────
# 📊 SAVE SUMMARY
# ─────────────────────────────────────────────
def save_summary_to_db(summary: list, file_id):
    """
    Save extraction summary rows to extracted_dataset.

    IMPORTANT: files_dataset only stores file metadata (file_name, file_path,
    file_type, file_size, upload_time, status, reason, doc_type).
    It has NO field_value / field_status / field_name columns.

    Extracted field data belongs in extracted_dataset which has:
        file_id, document_type, field_name, field_value, field_status, field_type
    """
    if not file_id:
        logger.warning("[DB] save_summary_to_db: no file_id provided — skipping")
        return

    if not summary:
        logger.warning(
            "[DB] save_summary_to_db: empty summary — nothing to insert | file_id=%s", file_id
        )
        return

    conn = None
    inserted = 0

    try:
        conn = _get_connection("save_summary_to_db")
        cur = conn.cursor()

        for i, row in enumerate(summary):
            if not isinstance(row, dict):
                logger.warning(
                    "[DB] save_summary_to_db: row %d is not a dict (got %s) — skipping",
                    i, type(row).__name__,
                )
                continue

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
                row.get("document_type", "INVOICE"),
                row.get("field_name"),
                str(row.get("field_values", "") or ""),
                row.get("field_status", "Missing"),
                row.get("field_type"),
            ))
            inserted += 1

        conn.commit()
        cur.close()
        logger.info(
            "[DB] save_summary_to_db complete | file_id=%s | inserted=%d/%d rows",
            file_id, inserted, len(summary),
        )

    except Exception as exc:
        logger.error(
            "[DB] save_summary_to_db failed | file_id=%s | error=%s", file_id, exc
        )
        if conn:
            conn.rollback()

    finally:
        if conn:
            conn.close()



# ─────────────────────────────────────────────
# 💾 SAVE TO EXTRACTED_DATASET
# ─────────────────────────────────────────────
# def save_to_extracted_dataset(summary: list, file_id=None):
#     """
#     Save extraction rows to extracted_dataset table.
#     Each row from generate_summary() is one field/value record.
#     """
#     if not file_id:
#         logger.warning("[DB] save_to_extracted_dataset: no file_id — skipping")
#         return

#     if not summary:
#         logger.warning(
#             "[DB] save_to_extracted_dataset: empty summary | file_id=%s", file_id
#         )
#         return

#     conn = _get_connection("save_to_extracted_dataset")
#     cursor = conn.cursor()

#     try:

#         for row in summary:

#             cursor.execute("""
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
#                 row.get("document_type", "INVOICE"),
#                 row.get("field_name"),
#                 row.get("field_values"),
#                 row.get("field_status"),
#                 row.get("field_type")
#             ))

#         conn.commit()
#         logger.info(
#             "[DB] save_to_extracted_dataset complete | file_id=%s | rows=%d",
#             file_id, len(summary),
#         )

#     except Exception as exc:
#         conn.rollback()
#         logger.error(
#             "[DB] save_to_extracted_dataset failed | file_id=%s | error=%s",
#             file_id, exc,
#         )

#     finally:
#         cursor.close()
#         conn.close()
