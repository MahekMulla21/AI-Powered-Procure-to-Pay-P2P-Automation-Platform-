# ─────────────────────────────────────────────────────────────
# decision_agent/postgres_checker.py
#
# All PostgreSQL queries.
# One function per table — reads only, never modifies your data.
# Plus fetch_latest_invoice() to get the most recent invoice
# from invoice_dataset for testing.
# ─────────────────────────────────────────────────────────────

import re
import json
import psycopg2
from datetime import datetime, date
from .config import DB_CONFIG


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except Exception:
            continue
    return None


def _to_float(value):
    if value is None:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(value).replace(",", ""))
        return float(cleaned) if cleaned else None
    except Exception:
        return None


def _row_to_dict(cur, row):
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


# ─────────────────────────────────────────────────────────────
# FETCH LATEST INVOICE FROM invoice_dataset
# Used by test_runner.py to get real data automatically
# ─────────────────────────────────────────────────────────────
def fetch_latest_invoice() -> dict | None:
    """
    Fetches the most recently inserted active invoice
    from invoice_dataset. Returns it as a dict so the
    decision agent can process it directly.
    """
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT
                invoice_number,
                vendor_name,
                invoice_date,
                due_date,
                po_reference_number,
                grn_reference,
                total_amount,
                tax,
                currency,
                company_code,
                status,
                file_id
            FROM invoice_dataset
            WHERE active_flag = 1
            ORDER BY id DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            print("[POSTGRES_CHECKER] No active invoice found in invoice_dataset")
            return None
        result = _row_to_dict(cur, row)
        print(f"[POSTGRES_CHECKER] Latest invoice fetched → {result.get('invoice_number')}")
        return result
    except Exception as e:
        print(f"[POSTGRES_CHECKER][ERROR] fetch_latest_invoice: {e}")
        return None
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────
# CHECK INVOICE — duplicate detection
# ─────────────────────────────────────────────────────────────
def check_invoice(invoice_number: str) -> dict | None:
    """Returns existing row if invoice already processed, else None."""
    if not invoice_number:
        return None
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT invoice_number, vendor_name, invoice_date,
                   po_reference_number, total_amount, status, active_flag
            FROM   invoice_dataset
            WHERE  invoice_number = %s
            AND    active_flag = 1
            LIMIT  1
        """, (invoice_number,))
        return _row_to_dict(cur, cur.fetchone())
    except Exception as e:
        print(f"[POSTGRES_CHECKER][ERROR] check_invoice: {e}")
        return None
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────
# CHECK PO — po_dataset
# ─────────────────────────────────────────────────────────────
def check_po(po_id: str) -> dict | None:
    """
    Returns active PO row from po_dataset.
    Schema written by po_postgres_writer.py:
      po_id, po_date, vendor_name, client_name, payment_terms, delivery_terms,
      currency, total_amount, start_date, end_date, reference_sow, reference_msa,
      quantity, unit_price, tax, tax_breakup, service_code, delivery_location,
      grn_indicator, po_status, active_flag, file_id
    """
    if not po_id:
        return None
    conn = get_connection()
    cur  = conn.cursor()
    try:
        # Normalise — strip whitespace and try exact match first
        po_id_clean = str(po_id).strip()
        cur.execute("""
            SELECT po_id, vendor_name, client_name, total_amount,
                   start_date, end_date, po_status,
                   reference_sow, reference_msa,
                   currency, payment_terms, active_flag
            FROM   po_dataset
            WHERE  LOWER(TRIM(po_id)) = LOWER(%s)
            AND    active_flag = 1
            LIMIT  1
        """, (po_id_clean,))
        row = _row_to_dict(cur, cur.fetchone())
        if row:
            row["start_date"]   = _parse_date(row.get("start_date"))
            row["end_date"]     = _parse_date(row.get("end_date"))
            row["total_amount"] = _to_float(row.get("total_amount"))
        return row
    except Exception as e:
        print(f"[POSTGRES_CHECKER][ERROR] check_po: {e}")
        return None
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────
# CHECK PR — pr_dataset
# ─────────────────────────────────────────────────────────────
def check_pr(pr_id: str) -> dict | None:
    """Returns active PR row by ID."""
    if not pr_id:
        return None
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT pr_id, vendor_name, approval_status AS status,
                   total_amount, department, request_date, required_date,
                   reference_sow_number, reference_msa_number, active_flag
            FROM   pr_dataset
            WHERE  LOWER(TRIM(pr_id)) = LOWER(%s) AND active_flag = 1
            LIMIT  1
        """, (str(pr_id).strip(),))
        return _row_to_dict(cur, cur.fetchone())
    except Exception as e:
        print(f"[POSTGRES_CHECKER][ERROR] check_pr: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def find_pr_by_reference(sow_id: str = None, msa_id: str = None) -> dict | None:
    """Finds an active PR linked to a specific SOW or MSA."""
    if not sow_id and not msa_id:
        return None
    conn = get_connection()
    cur  = conn.cursor()
    try:
        if sow_id:
            cur.execute("""
                SELECT pr_id, vendor_name, approval_status AS status,
                       total_amount, reference_sow_number, active_flag
                FROM   pr_dataset
                WHERE  LOWER(TRIM(reference_sow_number)) = LOWER(%s) AND active_flag = 1
                LIMIT  1
            """, (str(sow_id).strip(),))
        else:
            cur.execute("""
                SELECT pr_id, vendor_name, approval_status AS status,
                       total_amount, reference_msa_number, active_flag
                FROM   pr_dataset
                WHERE  LOWER(TRIM(reference_msa_number)) = LOWER(%s) AND active_flag = 1
                LIMIT  1
            """, (str(msa_id).strip(),))
        
        return _row_to_dict(cur, cur.fetchone())
    except Exception as e:
        print(f"[POSTGRES_CHECKER][ERROR] find_pr_by_reference: {e}")
        return None
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────
# CHECK MSA — msa_dataset
# ─────────────────────────────────────────────────────────────
def check_msa(msa_id: str) -> dict | None:
    """
    Returns active MSA row from msa_dataset.
    Schema written by MSA_postgres_writer.py:
      msa_id, vendor_name, vendor_id, start_date, end_date,
      status, created_by, currency, payment_terms,
      active_flag, file_id, start_timestamp, end_timestamp
    """
    if not msa_id:
        return None
    conn = get_connection()
    cur  = conn.cursor()
    try:
        msa_id_clean = str(msa_id).strip()
        cur.execute("""
            SELECT msa_id, vendor_name, vendor_id, status,
                   start_date, end_date, payment_terms,
                   currency, active_flag
            FROM   msa_dataset
            WHERE  LOWER(TRIM(msa_id)) = LOWER(%s)
            AND    active_flag = 1
            LIMIT  1
        """, (msa_id_clean,))
        row = _row_to_dict(cur, cur.fetchone())
        if row:
            row["start_date"] = _parse_date(row.get("start_date"))
            row["end_date"]   = _parse_date(row.get("end_date"))
        return row
    except Exception as e:
        print(f"[POSTGRES_CHECKER][ERROR] check_msa: {e}")
        return None
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────
# CHECK SOW — sow_dataset
# ─────────────────────────────────────────────────────────────
def check_sow(sow_id: str) -> dict | None:
    """
    Returns active SOW row from sow_dataset.
    Schema written by sow_db_writer.py:
      sow_id, reference_msa, vendor_id (also stores vendor_name here),
      start_date, end_date, status, unit_price, quantity,
      total_amount (NOT total_value), tax,
      active_flag, file_id, start_timestamp, end_timestamp
    Note: column is 'total_amount', NOT 'total_value'.
    """
    if not sow_id:
        return None
    conn = get_connection()
    cur  = conn.cursor()
    try:
        sow_id_clean = str(sow_id).strip()
        cur.execute("""
            SELECT sow_id, vendor_id AS vendor_name, status,
                   total_amount,
                   start_date, end_date,
                   reference_msa, active_flag
            FROM   sow_dataset
            WHERE  LOWER(TRIM(sow_id)) = LOWER(%s)
            AND    active_flag = 1
            LIMIT  1
        """, (sow_id_clean,))
        row = _row_to_dict(cur, cur.fetchone())
        if row:
            row["start_date"]  = _parse_date(row.get("start_date"))
            row["end_date"]    = _parse_date(row.get("end_date"))
            # Normalise: expose as total_value for rules_engine compatibility
            row["total_value"] = _to_float(row.get("total_amount"))
        return row
    except Exception as e:
        print(f"[POSTGRES_CHECKER][ERROR] check_sow: {e}")
        return None
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────
# SAVE VERDICT → invoice_decision_log
# Auto-creates table on first run
# ─────────────────────────────────────────────────────────────
def save_verdict(invoice_number: str, file_id, verdict: dict) -> None:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invoice_decision_log (
                id              SERIAL PRIMARY KEY,
                invoice_number  TEXT,
                file_id         INTEGER,
                verdict         TEXT,
                confidence      NUMERIC(5,3),
                reasons         JSONB,
                signals         JSONB,
                summary         TEXT,
                decided_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            INSERT INTO invoice_decision_log
                (invoice_number, file_id, verdict, confidence,
                 reasons, signals, summary)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
        """, (
            invoice_number,
            file_id,
            verdict.get("verdict"),
            verdict.get("confidence"),
            json.dumps(verdict.get("reasons", [])),
            json.dumps(verdict.get("signals", {}), default=str),
            verdict.get("summary", ""),
        ))
        conn.commit()
        print(f"[POSTGRES_CHECKER] Verdict saved → invoice_decision_log")
    except Exception as e:
        conn.rollback()
        print(f"[POSTGRES_CHECKER][ERROR] save_verdict: {e}")
    finally:
        cur.close()
        conn.close()
