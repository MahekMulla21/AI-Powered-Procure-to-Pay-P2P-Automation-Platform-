def is_digital_pdf(path: str) -> bool:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:3]:
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    return True
        return False
    except Exception:
        return True
