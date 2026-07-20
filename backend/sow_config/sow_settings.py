import os

# BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# OUTPUT_DIR = os.path.join(BASE_DIR, "faiss_db", "output")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR,"faiss_db","output")

INPUT_DIR  = os.path.join(BASE_DIR, "sow_data", "input")

# ─────────────────────────────────────────────────────────────
#  OLLAMA CONFIG
#  Server runs behind proxy on port 8080
#  Full API URL: http://10.1.1.219:8080/ollama/api/generate
# ─────────────────────────────────────────────────────────────
OLLAMA_URL     = "http://10.1.1.219:8080/ollama/api/generate"
OLLAMA_MODEL   = os.environ.get("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT = 120
API_KEY        = "sk-3dfeb7b956134897b247dd25457eebab"

#FAISS_INDEX_FILE = "sow_faiss_index.bin"
