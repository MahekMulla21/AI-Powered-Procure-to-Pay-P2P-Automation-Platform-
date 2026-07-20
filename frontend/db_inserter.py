# db_inserter.py

from db import get_connection
import traceback


# =====================================================
# 🔷 EXISTING DATA TABLES (NO CHANGE)
# =====================================================

def insert_invoice(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO invoice_data (
                vendor_name, invoice_number, invoice_date, due_date,
                hsn_code, quantity, unit_price, total_amount,
                tax, tax_breakup, currency
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data.get("vendor_name"),
            data.get("invoice_number"),
            data.get("invoice_date"),
            data.get("due_date"),
            data.get("hsn_code"),
            data.get("quantity"),
            data.get("unit_price"),
            data.get("total_amount"),
            data.get("tax"),
            data.get("tax_breakup"),
            data.get("currency")
        ))
        conn.commit()
    except:
        conn.rollback()
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()


def insert_pr(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO pr_data (
                pr_number, request_date, requested_by, department,
                vendor_name, budget_code, priority,
                total_amount, currency, required_date,
                reference_sow, reference_msa
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data.get("pr_number"),
            data.get("request_date"),
            data.get("requested_by"),
            data.get("department"),
            data.get("vendor_name"),
            data.get("budget_code"),
            data.get("priority"),
            data.get("total_amount"),
            data.get("currency"),
            data.get("required_date"),
            data.get("reference_sow"),
            data.get("reference_msa")
        ))
        conn.commit()
    except:
        conn.rollback()
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()


def insert_po(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO po_data (
                po_number, po_date, vendor_name, client_name,
                payment_terms, delivery_terms, currency,
                total_amount, start_date, end_date,
                reference_sow, reference_msa
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data.get("po_number"),
            data.get("po_date"),
            data.get("vendor_name"),
            data.get("client_name"),
            data.get("payment_terms"),
            data.get("delivery_terms"),
            data.get("currency"),
            data.get("total_amount"),
            data.get("start_date"),
            data.get("end_date"),
            data.get("reference_sow"),
            data.get("reference_msa")
        ))
        conn.commit()
    except:
        conn.rollback()
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()


def insert_sow(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO sow_data (
                service_name, service_description, scope_of_work,
                unit_price, quantity, total_amount,
                vendor_id, hsn_code, tax, tax_breakup,
                start_date, end_date, status
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data.get("service_name"),
            data.get("service_description"),
            data.get("scope_of_work"),
            data.get("unit_price"),
            data.get("quantity"),
            data.get("total_amount"),
            data.get("vendor_id"),
            data.get("hsn_code"),
            data.get("tax"),
            data.get("tax_breakup"),
            data.get("start_date"),
            data.get("end_date"),
            data.get("status")
        ))
        conn.commit()
    except:
        conn.rollback()
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()


# =====================================================
# 🔷 DATASET TABLES (WITH active_flag)
# =====================================================

def insert_msa_dataset(data, file_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE msa_dataset SET active_flag = 0 WHERE vendor_name = %s",
            (data.get("vendor_name"),)
        )

        cur.execute("""
            INSERT INTO msa_dataset (
                file_id, msa_id, vendor_name, vendor_id,
                start_date, end_date, status, created_by,
                currency, payment_terms, active_flag
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
        """, (
            file_id,
            data.get("msa_id"),
            data.get("vendor_name"),
            data.get("vendor_id"),
            data.get("start_date"),
            data.get("end_date"),
            data.get("status"),
            data.get("created_by"),
            data.get("currency"),
            data.get("payment_terms"),
        ))

        conn.commit()

    except:
        conn.rollback()
        traceback.print_exc()

    finally:
        cur.close()
        conn.close()


def insert_sow_dataset(data, file_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE sow_dataset SET active_flag = 0 WHERE sow_id = %s",
            (data.get("sow_id"),)
        )

        cur.execute("""
            INSERT INTO sow_dataset (
                file_id, sow_id, reference_msa, vendor_id,
                start_date, end_date, status,
                unit_price, quantity, total_amount, tax,
                active_flag
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
        """, (
            file_id,
            data.get("sow_id"),
            data.get("reference_msa"),
            data.get("vendor_id"),
            data.get("start_date"),
            data.get("end_date"),
            data.get("status"),
            data.get("unit_price"),
            data.get("quantity"),
            data.get("total_amount"),
            data.get("tax"),
        ))

        conn.commit()

    except:
        conn.rollback()
        traceback.print_exc()

    finally:
        cur.close()
        conn.close()


def insert_invoice_dataset(data, file_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE invoice_dataset SET active_flag = 0 WHERE invoice_number = %s",
            (data.get("invoice_number"),)
        )

        cur.execute("""
            INSERT INTO invoice_dataset (
                file_id, invoice_id, vendor_name, invoice_date,
                due_date, msa_reference, sow_reference,
                po_reference_number, grn_reference, hsn_code,
                quantity, unit_price, total_amount, tax,
                currency, company_code, status,
                tax_breakup, bank_details, active_flag, invoice_number
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)
        """, (
            file_id,
            data.get("invoice_id"),
            data.get("vendor_name"),
            data.get("invoice_date"),
            data.get("due_date"),
            data.get("msa_reference"),
            data.get("sow_reference"),
            data.get("po_reference_number"),
            data.get("grn_reference"),
            data.get("hsn_code"),
            data.get("quantity"),
            data.get("unit_price"),
            data.get("total_amount"),
            data.get("tax"),
            data.get("currency"),
            data.get("company_code"),
            data.get("status"),
            data.get("tax_breakup"),
            data.get("bank_details"),
            data.get("invoice_number"),
        ))

        conn.commit()

    except:
        conn.rollback()
        traceback.print_exc()

    finally:
        cur.close()
        conn.close()


def insert_pr_dataset(data, file_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO pr_dataset (
                file_id, pr_number, request_date, requested_by,
                department, vendor_name, total_amount, currency,
                active_flag
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1)
        """, (
            file_id,
            data.get("pr_number"),
            data.get("request_date"),
            data.get("requested_by"),
            data.get("department"),
            data.get("vendor_name"),
            data.get("total_amount"),
            data.get("currency"),
        ))

        conn.commit()

    except:
        conn.rollback()
        traceback.print_exc()

    finally:
        cur.close()
        conn.close()


# 🔥 FIXED PO DATASET (THIS WAS YOUR MAIN BUG)
def insert_po_dataset(data, file_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO po_dataset (
                file_id,   -- ✅ CRITICAL FIX
                po_number, po_date, vendor_name,
                total_amount, currency,
                reference_sow, reference_msa
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            file_id,
            data.get("po_number"),
            data.get("po_date"),
            data.get("vendor_name"),
            data.get("total_amount"),
            data.get("currency"),
            data.get("reference_sow"),
            data.get("reference_msa"),
        ))

        conn.commit()

    except:
        conn.rollback()
        traceback.print_exc()

    finally:
        cur.close()
        conn.close()

# =========================================
# ✅ SAVE MAIN DATA TABLE (FOR DATA MODE)
# =========================================

def save_main_table(doc_type, data, file_id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        if doc_type == "MSA":
            cur.execute("""
                INSERT INTO msa_data (file_id, vendor_name, start_date, end_date)
                VALUES (%s,%s,%s,%s)
            """, (
                file_id,
                data.get("vendor_name"),
                data.get("start_date"),
                data.get("end_date")
            ))

        elif doc_type == "SOW":
            cur.execute("""
                INSERT INTO sow_data (file_id, service_name, total_amount)
                VALUES (%s,%s,%s)
            """, (
                file_id,
                data.get("service_name"),
                data.get("total_amount")
            ))

        elif doc_type == "INVOICE":
            cur.execute("""
                INSERT INTO invoice_data (file_id, vendor_name, invoice_number)
                VALUES (%s,%s,%s)
            """, (
                file_id,
                data.get("vendor_name"),
                data.get("invoice_number")
            ))

        elif doc_type == "PR":
            cur.execute("""
                INSERT INTO pr_data (file_id, pr_number, vendor_name, total_amount)
                VALUES (%s,%s,%s,%s)
            """, (
                file_id,
                data.get("pr_number"),
                data.get("vendor_name"),
                data.get("total_amount")
            ))

        elif doc_type == "PO":
            cur.execute("""
                INSERT INTO po_data (file_id, po_number, vendor_name, total_amount)
                VALUES (%s,%s,%s,%s)
            """, (
                file_id,
                data.get("po_number"),
                data.get("vendor_name"),
                data.get("total_amount")
            ))

        conn.commit()
        print("✅ Main table inserted")

    except Exception as e:
        conn.rollback()
        print("❌ save_main_table error:", e)

    finally:
        cur.close()
        conn.close()