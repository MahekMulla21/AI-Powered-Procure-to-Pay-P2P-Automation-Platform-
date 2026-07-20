import psycopg2  # type: ignore[import]
import re
from datetime import datetime
from sow_config.sow_fields import (
    STRUCTURED_FIELDS,
    UNSTRUCTURED_FIELDS,
)

# ─────────────────────────────────────────────────────────────
#  DB CONNECTION
# ─────────────────────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(
        host="10.1.1.53",
        database="clrvw_db",
        user="postgres",
        password="postgres",
        port="5432"
    )


# ─────────────────────────────────────────────────────────────
#  DATE PARSER
# ─────────────────────────────────────────────────────────────

def parse_date(d):
    if not d:
        return None
    if isinstance(d, datetime):
        return d
    d = str(d).strip()
    for fmt in (
        "%Y-%m-%d",
        "%B %d, %Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(d, fmt)
        except Exception:
            continue
    return None


# ─────────────────────────────────────────────────────────────
#  NUMERIC CLEANER
# ─────────────────────────────────────────────────────────────

def to_float(value):
    if not value:
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


# ─────────────────────────────────────────────────────────────
#  FIELD LISTS
# ─────────────────────────────────────────────────────────────

SUMMARY_FIELDS = [
    ("sow_id",                "sow_id"),
    ("reference_msa",         "reference_msa"),
    ("vendor_id",             "vendor_id"),
    ("vendor_name",           "vendor_name"),
    ("client_name",           "client_name"),
    ("project_title",         "project_title"),
    ("start_date",            "start_date"),
    ("end_date",              "end_date"),
    ("payment_terms",         "payment_terms"),
    ("currency",              "currency"),
    ("status",                "status"),
    ("total_amount",          "total_amount"),
    ("service_description",   "service_description"),
    ("scope_of_work",         "scope_of_work"),
    ("deliverables",          "deliverables"),
    ("payment_schedule",      "payment_schedule"),
    ("resource_requirements", "resource_requirements"),
    ("acceptance_criteria",   "acceptance_criteria"),
    ("termination_clause",    "termination_clause"),
]

# Columns compared for duplicate and update detection
COMPARE_COLUMNS = [
    "reference_msa",
    "vendor_id",
    "start_date",
    "end_date",
    "status",
    "unit_price",
    "quantity",
    "total_amount",
    "tax",
]


# ─────────────────────────────────────────────────────────────
#  NORMALISE HELPER
# ─────────────────────────────────────────────────────────────

def _norm(val) -> str:
    """Lowercase stripped string for safe comparison."""
    if val is None:
        return ""
    return str(val).strip().lower()


# ─────────────────────────────────────────────────────────────
#  AUTO MIGRATION
# ─────────────────────────────────────────────────────────────

def _ensure_active_flag(cur):
    """Add active_flag and SCD Type 2 timestamp columns if they do not exist."""
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'sow_dataset' AND column_name = 'active_flag'
    """)
    if cur.fetchone() is None:
        cur.execute("ALTER TABLE sow_dataset ADD COLUMN active_flag INT DEFAULT 1")
        cur.execute("UPDATE sow_dataset SET active_flag = 1 WHERE active_flag IS NULL")
        print("  [MIGRATION] active_flag column added to sow_dataset.")

    # ── SCD Type 2 timestamp columns ──────────────────────────
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'sow_dataset' AND column_name = 'start_timestamp'
    """)
    if cur.fetchone() is None:
        cur.execute("ALTER TABLE sow_dataset ADD COLUMN start_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        cur.execute("ALTER TABLE sow_dataset ADD COLUMN end_timestamp TIMESTAMP DEFAULT NULL")
        print("  [MIGRATION] start_timestamp & end_timestamp columns added to sow_dataset.")

# ─────────────────────────────────────────────────────────────
#  CHECK IF ACTIVE RECORD EXISTS
# ─────────────────────────────────────────────────────────────

def check_sow_exists(cur, sow_id) -> bool:
    """Returns True if an active record exists for this sow_id."""
    cur.execute(
        """
        SELECT COUNT(*) FROM sow_dataset
        WHERE sow_id = %s AND active_flag = 1
        """,
        (sow_id,)
    )
    return cur.fetchone()[0] > 0


# ─────────────────────────────────────────────────────────────
#  FETCH ACTIVE ROW FOR COMPARISON
# ─────────────────────────────────────────────────────────────

def fetch_active_sow(cur, sow_id):
    """Fetch the current active row as a dict for comparison."""
    cur.execute(
        """
        SELECT sow_id,
               reference_msa,
               vendor_id,
               start_date::text,
               end_date::text,
               status,
               unit_price::text,
               quantity::text,
               total_amount::text,
               tax::text,
               active_flag
        FROM sow_dataset
        WHERE sow_id = %s AND active_flag = 1
        LIMIT 1
        """,
        (sow_id,)
    )
    cols = [desc[0] for desc in cur.description]
    row  = cur.fetchone()
    return dict(zip(cols, row)) if row else None


# ─────────────────────────────────────────────────────────────
#  DUPLICATE CHECK — 100% field match
# ─────────────────────────────────────────────────────────────

def is_duplicate(cur, sow_id: str, new_data: dict) -> bool:
    """
    Fetch active DB row, normalise both sides to same format,
    then compare column by column in Python.
    Date format mismatch is handled by parsing both to YYYY-MM-DD.
    """

    def norm_id(val):
        if not val:
            return ""
        tokens = str(val).strip().split()
        real = next(
            (t for t in tokens if "-" in t and any(c.isdigit() for c in t)),
            tokens[-1] if tokens else ""
        )
        return real.strip().lower()

    def norm_status(val):
        if not val:
            return "active"
        v = str(val).lower()
        for s in ["active", "inactive", "closed", "draft", "expired", "completed"]:
            if s in v:
                return s
        return "active"

    def norm_date(val):
        if not val:
            return ""
        if isinstance(val, str) and re.match(r"^\d{4}-\d{2}-\d{2}", val):
            return val[:10]
        d = parse_date(val)
        return d.strftime("%Y-%m-%d") if d else str(val).strip().lower()

    def norm_num(val):
        f = to_float(val)
        if f is None:
            return ""
        return f"{f:.2f}"

    # Fetch current active DB row
    cur.execute(
        """
        SELECT reference_msa,
               vendor_id,
               start_date::text,
               end_date::text,
               status,
               unit_price::text,
               quantity::text,
               total_amount::text,
               tax::text
        FROM sow_dataset
        WHERE sow_id = %s AND active_flag = 1
        LIMIT 1
        """,
        (sow_id,)
    )
    row = cur.fetchone()
    if not row:
        return False

    db = dict(zip(
        ["reference_msa", "vendor_id", "start_date", "end_date",
         "status", "unit_price", "quantity", "total_amount", "tax"],
        row
    ))

    # Normalise NEW data
    new_norm = {
        "reference_msa": norm_id(new_data.get("reference_msa")),
        "vendor_id":     norm_id(new_data.get("vendor_id") or new_data.get("vendor_name")),
        "start_date":    norm_date(new_data.get("start_date")),
        "end_date":      norm_date(new_data.get("end_date")),
        "status":        norm_status(new_data.get("status")),
        "unit_price":    norm_num(new_data.get("unit_price")),
        "quantity":      norm_num(new_data.get("quantity")),
        "total_amount":  norm_num(new_data.get("total_amount")),
        "tax":           norm_num(new_data.get("tax")),
    }

    # Normalise DB row
    db_norm = {
        "reference_msa": norm_id(db.get("reference_msa")),
        "vendor_id":     norm_id(db.get("vendor_id")),
        "start_date":    norm_date(db.get("start_date")),
        "end_date":      norm_date(db.get("end_date")),
        "status":        norm_status(db.get("status")),
        "unit_price":    norm_num(db.get("unit_price")),
        "quantity":      norm_num(db.get("quantity")),
        "total_amount":  norm_num(db.get("total_amount")),
        "tax":           norm_num(db.get("tax")),
    }

    # Compare column by column
    all_match = True
    for col in new_norm:
        nv = new_norm[col]
        dv = db_norm[col]
        match = (nv == dv)
        print(f"  [COL] {col:<20} extracted='{nv}'  db='{dv}'  match={match}")
        if not match:
            all_match = False

    print(f"  [RESULT] {'DUPLICATE — file rejected' if all_match else 'NOT duplicate — will update'}")
    return all_match


# ─────────────────────────────────────────────────────────────
#  DEACTIVATE OLD RECORD
# ─────────────────────────────────────────────────────────────

def deactivate_old_sow(cur, sow_id):
    """SCD Type 2: Close active row by stamping end_timestamp and setting active_flag = 0."""
    cur.execute(
        """
        UPDATE sow_dataset
        SET active_flag   = 0,
            end_timestamp = %s        -- ← stamp closure time
        WHERE sow_id = %s AND active_flag = 1
        """,
        (datetime.now(), sow_id)
    )
    print(f"  [DEACTIVATE] sow_id={sow_id} → active_flag=0, end_timestamp={datetime.now()}")

# ─────────────────────────────────────────────────────────────
#  INSERT NEW ROW INTO sow_dataset
#  Carries forward non-null values from existing DB row
#  so we never overwrite good data with null.
# ─────────────────────────────────────────────────────────────

#def insert_sow(cur, data: dict, active_flag: int = 1, existing_row: dict = None):
def insert_sow(cur, data: dict, active_flag: int = 1, existing_row: dict = None, file_id=None):

    """
    Insert one row into sow_dataset.
    If existing_row is provided (UPDATE case), any field that is null
    in new extracted data is filled from the existing DB row.
    This prevents losing previously extracted good data.
    """

    def clean_status(val):
        if not val:
            return "Active"
        known = ["Active", "Inactive", "Closed", "Draft", "Expired", "Completed"]
        for s in known:
            if s.lower() in str(val).lower():
                return s
        return "Active"

    def clean_id(val):
        if not val:
            return None
        tokens = str(val).split()
        real = next(
            (t for t in tokens if "-" in t and any(c.isdigit() for c in t)),
            tokens[-1] if tokens else val
        )
        return real.strip() or None

    def best_val(new_val, old_val, cleaner=None):
        """
        Pick the best value between new extraction and existing DB row.
        New value wins if it is non-null and non-empty.
        Otherwise fall back to old DB value so we never save null
        over a good existing value.
        """
        cleaned = cleaner(new_val) if cleaner else (new_val or "").strip() or None
        if cleaned:
            return cleaned
        # Fall back to old DB value
        return old_val if old_val and str(old_val).strip() not in ("", "None", "null") else None

    def best_date(new_val, old_val):
        """Pick best date — new if parseable, else carry forward old."""
        parsed_new = parse_date(new_val)
        if parsed_new:
            return parsed_new
        parsed_old = parse_date(old_val)
        if parsed_old:
            print(f"  [CARRY] date null in new doc → kept '{old_val}' from DB")
            return parsed_old
        return None

    def best_num(new_val, old_val):
        """Pick best numeric — new if parseable, else carry forward old."""
        n = to_float(new_val)
        if n is not None:
            return n
        o = to_float(old_val)
        return o  # may also be None if both missing

    # ── Get old values to carry forward (empty dict if NEW insert) ──
    old = existing_row or {}

    # ── Resolve each field ──────────────────────────────────────────
    sow_id        = best_val(data.get("sow_id"),        old.get("sow_id"),        clean_id)
    reference_msa = best_val(data.get("reference_msa"), old.get("reference_msa"), clean_id)
    vendor_id     = best_val(
                        data.get("vendor_id") or data.get("vendor_name"),
                        old.get("vendor_id"),
                        clean_id
                    )
    start_date    = best_date(data.get("start_date"), old.get("start_date"))
    end_date      = best_date(data.get("end_date"),   old.get("end_date"))
    status        = clean_status(
                        data.get("status") or old.get("status")
                    )
    unit_price    = best_num(data.get("unit_price"),    old.get("unit_price"))
    quantity      = best_num(data.get("quantity"),      old.get("quantity"))
    total_amount  = best_num(data.get("total_amount"),  old.get("total_amount"))
    tax           = best_num(data.get("tax"),           old.get("tax"))

    # ── Log what was carried forward ────────────────────────────────
    if old:
        carry_checks = [
            ("reference_msa", data.get("reference_msa"), old.get("reference_msa")),
            ("vendor_id",     data.get("vendor_id"),     old.get("vendor_id")),
            ("start_date",    data.get("start_date"),    old.get("start_date")),
            ("end_date",      data.get("end_date"),      old.get("end_date")),
            ("total_amount",  data.get("total_amount"),  old.get("total_amount")),
        ]
        for field, new_v, old_v in carry_checks:
            if not new_v and old_v:
                print(f"  [CARRY] {field}: null in new doc → kept '{old_v}' from DB")

    # Update the query inside insert_sow:
    query = """
        INSERT INTO sow_dataset (
            sow_id,
            reference_msa,
            vendor_id,
            start_date,
            end_date,
            status,
            unit_price,
            quantity,
            total_amount,
            tax,
            active_flag,
            file_id,
            start_timestamp,        -- ← ADD
            end_timestamp           -- ← ADD
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        sow_id,
        reference_msa,
        vendor_id,
        start_date,
        end_date,
        status,
        unit_price,
        quantity,
        total_amount,
        tax,
        active_flag,
        file_id,
        datetime.now(),             # ← start_timestamp = NOW()
        None                        # ← end_timestamp = NULL (active record)
    )

    print("  [INSERT] Inserting into sow_dataset...")
    cur.execute(query, values)


# ─────────────────────────────────────────────────────────────
#  SAVE TO extracted_dataset AUDIT TABLE
# ─────────────────────────────────────────────────────────────

def save_extracted_data(cur, structured: dict, file_id):

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

    for field_name, data_key in SUMMARY_FIELDS:

        value = structured.get(data_key)

        if data_key in STRUCTURED_FIELDS:
            field_type = "structured"
        elif data_key in UNSTRUCTURED_FIELDS:
            field_type = "unstructured"
        else:
            field_type = "UNKNOWN"

        is_na = value and any(x in str(value) for x in [
            "Not Applicable",
            "Not Mentioned",
            "No Tax",
            "No Tax Breakup"
        ])

        if is_na:
            fv, fs = "NA", "N/A"
        elif not value:
            fv, fs = "NA", "Missing"
        else:
            fv, fs = str(value).strip(), "Valid"

        cur.execute(
            query,
            (
                file_id,
                "SOW",
                field_name,
                fv,
                fs,
                field_type,
            )
        )

    print(f"  [extracted_dataset] {len(SUMMARY_FIELDS)} audit rows saved.")

# ─────────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────

# def save_to_postgres(structured: dict, file_id=None) -> dict:
def save_to_postgres(structured: dict, file_id=None, pre_status: str = None) -> dict:
    """
    Main entry point called from sow_main.py.

    Decision flow:
      STEP 1 — Save audit rows to extracted_dataset (always).
      STEP 2 — Check if active record exists for this sow_id.
      STEP 3 — If EXISTS:
                 Compare field by field.
                 ALL identical  → DUPLICATE → REJECT.
                 Any different  → UPDATE:
                                   old row active_flag = 0
                                   new row active_flag = 1
                                   carry forward any null fields from old row
      STEP 4 — If NOT EXISTS:
                 NEW → Insert fresh record with active_flag = 1.
    """
    conn = None
    cur  = None

    try:
        print("\n  [DB] Connecting to PostgreSQL...")
        print(f"  [DEBUG] file_id received = {file_id}")
        # Get sow_id — use filename-based fallback for stable ID
        sow_id = structured.get("sow_id")
        if not sow_id:
            import uuid
            sow_id = f"SOW-AUTO-{str(uuid.uuid4())[:8].upper()}"
            structured["sow_id"] = sow_id
            print(f"  [WARN] sow_id not found — generated: {sow_id}")

        conn = get_connection()
        cur  = conn.cursor()

        # Auto-add active_flag column if missing
        _ensure_active_flag(cur)

        # STEP 1 — Always save audit rows
        save_extracted_data(cur, structured, file_id)

        # STEP 2 — Check if active record exists
        exists = check_sow_exists(cur, sow_id)

        # if exists:
        #     print(f"  [CHECK] Active record found for sow_id={sow_id}")

        #     # Fetch existing row for comparison AND carry-forward
        #     db_row = fetch_active_sow(cur, sow_id)

        #     if is_duplicate(cur, sow_id, structured):
        #         # DUPLICATE — reject, nothing inserted
        #         print(f"  [DUPLICATE] sow_id={sow_id} — all fields identical. File REJECTED.")
        #         conn.commit()
        #         return {
        #             "action":  "DUPLICATE",
        #             "sow_id":  sow_id,
        #             "message": "All fields match existing record — file REJECTED.",
        #         }

        #     else:
        #         # UPDATE — deactivate old, insert new with carry-forward
        #         print(f"  [UPDATE] Change detected for sow_id={sow_id}")
        #         deactivate_old_sow(cur, sow_id)
        #         # Pass existing_row so nulls are filled from old DB values
        #         insert_sow(cur, structured, active_flag=1, existing_row=db_row)
        #         conn.commit()
        #         print(f"  [UPDATE] New record inserted with active_flag=1.")
        #         return {
        #             "action": "UPDATE",
        #             "sow_id": sow_id,
        #         }

        # else:
        #     # STEP 4 — NEW: no existing record
        #     print(f"  [NEW] No existing record for sow_id={sow_id}")
        #     # No existing_row — only use what was extracted
        #     insert_sow(cur, structured, active_flag=1, existing_row=None)
        #     conn.commit()
        #     print(f"  [NEW] Record inserted with active_flag=1.")
        #     return {
        #         "action": "NEW",
        #         "sow_id": sow_id,
        #     }
    # ── Use pre-computed status from Step 5 if provided ──────────
        if pre_status is None:
            # fallback: compute status here if not passed
            if exists:
                db_dup = is_duplicate(cur, sow_id, structured)
                pre_status = "DUPLICATE" if db_dup else "REVIEW_REQUIRED"
            else:
                pre_status = "NEW"

        print(f"  [DB] Using status: {pre_status}")

        if pre_status == "DUPLICATE":
            print(f"  [DUPLICATE] sow_id={sow_id} — all fields identical. File REJECTED.")
            conn.commit()
            return {
                "action":  "DUPLICATE",
                "sow_id":  sow_id,
                "message": "All fields match existing record — file REJECTED.",
            }

        elif pre_status == "REVIEW_REQUIRED":
            print(f"  [UPDATE] Change detected for sow_id={sow_id}")
            db_row = fetch_active_sow(cur, sow_id)
            deactivate_old_sow(cur, sow_id)
            insert_sow(cur, structured, active_flag=1, existing_row=db_row, file_id=file_id)
            conn.commit()
            print(f"  [UPDATE] Old record active_flag=0. New record inserted with active_flag=1.")
            return {
                "action": "UPDATE",
                "sow_id": sow_id,
            }

        else:  # NEW
            print(f"  [NEW] No existing record for sow_id={sow_id}")
            insert_sow(cur, structured, active_flag=1, existing_row=None, file_id=file_id)
            conn.commit()
            print(f"  [NEW] Record inserted with active_flag=1.")
            return {
                "action": "NEW",
                "sow_id": sow_id,
            }
    except Exception as e:
        import traceback
        print("\n  [ERROR] DB ERROR:")
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
        print("  [DB] Connection closed.")