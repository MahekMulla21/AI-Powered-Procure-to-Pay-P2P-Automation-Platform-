import os
from paddleocr import PaddleOCR
from PIL import Image
import numpy as np

# Singleton OCR instance
_ocr_instance = None


def get_ocr():
    global _ocr_instance

    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,
            lang="en",
            show_log=False
        )

    return _ocr_instance


def extract_text(image_path: str) -> str:
    """
    Extract text from image using PaddleOCR.
    """

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    ocr = get_ocr()

    result = ocr.ocr(image_path, cls=True)

    lines = []

    if result:
        for block in result:
            if not block:
                continue

            for line in block:
                try:
                    text = line[1][0]
                    if text:
                        lines.append(text)
                except Exception:
                    continue

    return "\n".join(lines)