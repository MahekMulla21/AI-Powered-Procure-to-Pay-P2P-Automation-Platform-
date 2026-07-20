from Invoice_ocr.Invoice_pdf_text_extractor import extract_text_from_pdf

def is_digital_pdf(pdf_path, threshold=100):
    text = extract_text_from_pdf(pdf_path)

    # If enough readable text → digital
    return len(text.strip()) > threshold