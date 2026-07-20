import os

# ─────────────────────────────────────────────
# 📁 BASE PATHS
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR,"faiss_db","output")
INPUT_DIR  = os.path.join(BASE_DIR, "PO_data", "input")
IMAGE_DIR  = os.path.join(BASE_DIR, "PO_data", "images")

# ─────────────────────────────────────────────
# 📄 FILE PATHS
# ─────────────────────────────────────────────
PDF_PATH        = os.path.join(INPUT_DIR,  "po.pdf")
EXCEL_OUTPUT    = os.path.join(OUTPUT_DIR, "structured.xlsx")
RAW_TEXT_OUTPUT = os.path.join(OUTPUT_DIR, "raw_text.txt")

# ─────────────────────────────────────────────
# 🤖 MODEL CONFIG
# ─────────────────────────────────────────────
MODEL_NAME = "llama3"


# ─────────────────────────────────────────────
# 🗃️ DATABASE CONFIG
# ─────────────────────────────────────────────
DB_CONFIG = {
    "host":     "10.1.1.53",
    "database": "clrvw_db",
    "user":     "postgres",
    "password": "postgres",
    "port":     "5432"
}

# ─────────────────────────────────────────────
# 🧾 PO — STRUCTURED FIELDS
# ─────────────────────────────────────────────
PO_STRUCTURED_FIELDS = [
    "po_id",
    "po_date",
    "vendor_name",
    "client_name",
    "payment_terms",
    "delivery_terms",
    "currency",
    "total_amount",
    "start_date",
    "end_date",
    "reference_sow",
    "reference_msa",
    "quantity",
    "unit_price",
    "tax",
    "tax_breakup",
    "service_code",
    "delivery_location",
    "grn_indicator",
    "po_status"
]

# ─────────────────────────────────────────────
# 📝 PO — UNSTRUCTURED FIELDS
# ─────────────────────────────────────────────
PO_UNSTRUCTURED_FIELDS = [
    "description_of_goods_and_services"
]

# ─────────────────────────────────────────────
# 🗄️ TABLE NAMES
# ─────────────────────────────────────────────
TABLE_PO     = "po_dataset"
TABLE_FILES  = "files_dataset"

# ─────────────────────────────────────────────
# 🔧 ENSURE OUTPUT DIRECTORIES EXIST
# ─────────────────────────────────────────────
for _dir in [INPUT_DIR, IMAGE_DIR, OUTPUT_DIR]:
    os.makedirs(_dir, exist_ok=True)