def pdf_to_images(pdf_path: str) -> list:
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=300)
        print(f"  Converted {len(images)} pages to images")
        return images
    except ImportError:
        raise ImportError("Run: pip install pdf2image")
