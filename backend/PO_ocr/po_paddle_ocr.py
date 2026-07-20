from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, lang='en')

def extract_text(image_paths):
    full_text = ""

    for img_path in image_paths:
        result = ocr.ocr(img_path)

        if result[0]:
            for line in result[0]:
                text = line[1][0]
                full_text += text + "\n"

    return full_text