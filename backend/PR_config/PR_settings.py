import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR,"faiss_db","output")
PDF_PATH = os.path.join(BASE_DIR, "PR_data/input/msa.pdf")
IMAGE_DIR = os.path.join(BASE_DIR, "PR_data/images/")


MODEL_NAME = "llama3"
API="sk-b2fec1202df44aec868c8eab5b767ba6"
URL="http://10.1.1.219:8080/ollama/api/generate"

EXCEL_OUTPUT = os.path.join(OUTPUT_DIR, "structured.xlsx")
RAW_TEXT_OUTPUT = os.path.join(OUTPUT_DIR, "raw_text.txt")

FAISS_INDEX_PATH = os.path.join(OUTPUT_DIR, "pr.index")




#DB Configuration
DB_CONFIG = {
        "host": "10.1.1.53",
        "database": "clrvw_db",
        "user": "postgres",
        "password": "postgres"
}