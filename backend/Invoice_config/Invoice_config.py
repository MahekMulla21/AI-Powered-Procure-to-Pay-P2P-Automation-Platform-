# Invoice_config.py
# ─────────────────────────────────────────────────────────────────
# Central configuration for the Invoice Extractor System.
# All environment-specific settings live here — no hardcoding
# anywhere else in the codebase.
# ─────────────────────────────────────────────────────────────────

# ── LLM / API  (Local Ollama – llama3) ───────────────────────────
# Prerequisites:
#   1. Install Ollama  → https://ollama.com/download
#   2. Pull the model  → ollama pull llama3
#   3. Ollama starts automatically; or run manually → ollama serve
OLLAMA_API_URL  = "http://localhost:11434/v1/chat/completions"
OLLAMA_API_KEY  = "ollama"          # Ollama ignores the key; any non-empty string works
OLLAMA_MODEL    = "llama3"          # must match the name used in: ollama pull llama3
LLM_TEMPERATURE = 0
LLM_TIMEOUT_SEC = 120               # local models can be slower on first call; 120s is safe

# ── OCR ──────────────────────────────────────────────────────────
OCR_DPI                  = 200      # DPI for Tesseract fallback rasterisation
OCR_LANGUAGE             = "eng"
OCR_MIN_CHAR_THRESHOLD   = 50       # if pdfplumber returns fewer chars → use Tesseract

# ── FAISS (TF-IDF) ───────────────────────────────────────────────
CHUNK_SIZE    = 720                 # words per chunk
CHUNK_OVERLAP = 80                  # word overlap between consecutive chunks
FAISS_TOP_K   = 4                   # default top-k for semantic search

# ── Paths ────────────────────────────────────────────────────────
DEFAULT_PDF_PATH   = "data/input/invoice.pdf"
OUTPUT_JSON_PATH   = "data/output/invoice_extraction_result.json"

# ── System prompt for LLM ────────────────────────────────────────
LLM_SYSTEM_PROMPT = "You are an expert invoice data extractor. Be concise and precise."
