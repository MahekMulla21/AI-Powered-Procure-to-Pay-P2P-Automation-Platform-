def extract_text(images: list) -> str:
    if not images:
        return ""
    all_text = []
    for i, img in enumerate(images):
        try:
            import pytesseract
            text = pytesseract.image_to_string(img)
            all_text.append(text)
        except ImportError:
            raise ImportError("Run: pip install pytesseract")
    return "\n".join(all_text)
