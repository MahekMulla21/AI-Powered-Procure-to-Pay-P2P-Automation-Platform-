import fitz  # PyMuPDF
import numpy as np
from PIL import Image


# ===============================
# PDF TO IMAGES
# ===============================
def pdf_to_images(file_path, dpi=200):
    """
    Convert PDF pages to images using PyMuPDF (fitz).
    No pdf2image or Poppler required.

    Args:
        file_path (str): Path to PDF file
        dpi (int):       Resolution for rendering (default 200)

    Returns:
        list: List of PIL Image objects
    """

    images = []

    try:

        # ===============================
        # OPEN PDF
        # ===============================
        pdf_document = fitz.open(file_path)

        print(
            f"[PDF→IMAGE] Total pages: {len(pdf_document)}"
        )

        # ===============================
        # RENDER EACH PAGE
        # ===============================
        for page_num in range(len(pdf_document)):

            page = pdf_document[page_num]

            # DPI → zoom matrix
            zoom = dpi / 72
            mat  = fitz.Matrix(zoom, zoom)

            # Render page to pixel map
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            images.append(img)

            print(
                f"[PDF→IMAGE] Page {page_num + 1} "
                f"→ {pix.width}x{pix.height}px"
            )

        pdf_document.close()

        print(
            f"[PDF→IMAGE] Done. {len(images)} image(s) extracted"
        )

    except Exception as e:

        print(f"[ERROR] PDF to image conversion failed: {e}")

    return images