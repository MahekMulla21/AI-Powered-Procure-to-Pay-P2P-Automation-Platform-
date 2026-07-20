from pdf2image import convert_from_path
import os
from MSA_config.MSA_settings import IMAGE_DIR

def pdf_to_images(pdf_path):
    os.makedirs(IMAGE_DIR, exist_ok=True)

    images = convert_from_path(pdf_path)
    image_paths = []

    for i, img in enumerate(images):
        path = os.path.join(IMAGE_DIR, f"page_{i}.png")
        img.save(path, "PNG")
        image_paths.append(path)

    return image_paths