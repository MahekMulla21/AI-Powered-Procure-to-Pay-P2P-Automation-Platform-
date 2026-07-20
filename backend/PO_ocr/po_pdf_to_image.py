import fitz  # pymupdf
import os
from PO_config.po_settings import IMAGE_DIR


def pdf_to_images(pdf_path):
    """
    Converts each page of a PDF to a PNG image using PyMuPDF.
    No Poppler or external binaries required.
    """
    os.makedirs(IMAGE_DIR, exist_ok=True)

    image_paths = []
    pdf_document = fitz.open(pdf_path)

    for i, page in enumerate(pdf_document):

        # ── Render page to image (2x zoom = 144 DPI) ──
        mat  = fitz.Matrix(2.0, 2.0)
        pix  = page.get_pixmap(matrix=mat, alpha=False)

        path = os.path.join(IMAGE_DIR, f"page_{i}.png")
        pix.save(path)

        image_paths.append(path)
        print(f"[IMAGE] Page {i + 1} saved → {path}")

    pdf_document.close()

    print(f"[IMAGE] Total pages converted: {len(image_paths)}")
    return image_paths