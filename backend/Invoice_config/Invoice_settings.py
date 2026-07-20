import os

# ─────────────────────────────────────────────
# 📁 BASE PATHS
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR        = os.path.join(BASE_DIR, "faiss_db", "output")
FAISS_INDEX_PATH  = os.path.join(OUTPUT_DIR, "global_faiss.index")
FAISS_MAPPING_PATH = os.path.join(OUTPUT_DIR, "global_faiss_mapping.pkl")
INPUT_DIR  = os.path.join(BASE_DIR, "Invoice_data", "input")
IMAGE_DIR  = os.path.join(BASE_DIR, "Invoice_data", "images")

# ─────────────────────────────────────────────
# 📄 FILE PATHS
# ─────────────────────────────────────────────
PDF_PATH        = os.path.join(INPUT_DIR,  "invoice.pdf")
EXCEL_OUTPUT    = os.path.join(OUTPUT_DIR, "structured.xlsx")
RAW_TEXT_OUTPUT = os.path.join(OUTPUT_DIR, "raw_text.txt")

# ─────────────────────────────────────────────
# 🤖 MODEL CONFIG
# ─────────────────────────────────────────────
MODEL_NAME = "llama3"
API_KEY    = "sk-b2fec1202df44aec868c8eab5b767ba6"
API_URL    = "http://10.1.1.219:8080/ollama/api/generate"


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
# 🧾 INVOICE — STRUCTURED FIELDS
# ─────────────────────────────────────────────
INVOICE_STRUCTURED_FIELDS = [
    "invoice_number",
    "vendor_name",
    "invoice_date",
    "due_date",
    "po_reference_number",
    "grn_reference",
    "hsn_code",
    "quantity",
    "unit_price",
    "total_amount",
    "tax",
    "currency",
    "company_code",
    "status"
]

# ─────────────────────────────────────────────
# 📝 INVOICE — UNSTRUCTURED FIELDS
# ─────────────────────────────────────────────
INVOICE_UNSTRUCTURED_FIELDS = [
    "tax_breakup",
    "bank_details",
    "description_of_service"
]

# ─────────────────────────────────────────────
# 🗄️ TABLE NAMES
# ─────────────────────────────────────────────
TABLE_INVOICE  = "invoice_dataset"
TABLE_FILES    = "files_dataset"

# ─────────────────────────────────────────────
# 🔧 ENSURE OUTPUT DIRECTORIES EXIST
# ─────────────────────────────────────────────
for _dir in [INPUT_DIR, IMAGE_DIR, OUTPUT_DIR]:
    os.makedirs(_dir, exist_ok=True)