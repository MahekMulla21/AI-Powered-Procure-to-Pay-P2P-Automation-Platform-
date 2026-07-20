# Invoice_ocr.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# ─────────────────────────────────────────────────────────────────
# OCR Layer — extracts raw text from a PDF file.
#
# Strategy:
#   1. Try pdfplumber (fast, lossless for text-layer PDFs)
#   2. If output is too short → fall back to pytesseract (scanned PDFs)
# ─────────────────────────────────────────────────────────────────
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
import pdfplumber
import pytesseract # type: ignore
from pdf2image import convert_from_path # type: ignore
from PIL import Image

from backend.Invoice_config.Invoice_config import (
    OCR_DPI,
    OCR_LANGUAGE,
    OCR_MIN_CHAR_THRESHOLD,
)


# ── Primary: pdfplumber ───────────────────────────────────────────

def extract_text_pdfplumber(pdf_path: str) -> str:
    """
    Extract text from a native (text-layer) PDF using pdfplumber.
    Returns concatenated page text separated by double newlines.
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
    return "\n\n".join(pages)


# ── Fallback: Tesseract OCR ───────────────────────────────────────

def extract_text_tesseract(pdf_path: str) -> str:
    """
    Rasterise each PDF page at OCR_DPI and run Tesseract OCR.
    Used when pdfplumber returns insufficient text (scanned PDFs).
    """
    images = convert_from_path(pdf_path, dpi=OCR_DPI)
    pages  = []
    for img in images:
        text = pytesseract.image_to_string(img, lang=OCR_LANGUAGE)
        pages.append(text.strip())
    return "\n\n".join(pages)


# ── Public interface ──────────────────────────────────────────────

def extract_text(pdf_path: str) -> str:
    """
    Main OCR entry point.

    1. Run pdfplumber.
    2. Count non-whitespace characters.
    3. If below OCR_MIN_CHAR_THRESHOLD → switch to Tesseract.

    Returns the full extracted text string.
    """
    text = extract_text_pdfplumber(pdf_path)
    meaningful_chars = len(text.replace(" ", "").replace("\n", ""))

    if meaningful_chars < OCR_MIN_CHAR_THRESHOLD:
        print("[OCR] pdfplumber yielded insufficient text → switching to Tesseract OCR …")
        text = extract_text_tesseract(pdf_path)
        print(f"[OCR] Tesseract complete. {len(text)} characters extracted.")
    else:
        print(f"[OCR] pdfplumber success. {len(text)} characters extracted.")

    return text
