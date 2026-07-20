import os
import pdfplumber
import shutil
from datetime import datetime

# Optional (install if needed)
try:
    import docx
except:
    docx = None

try:
    from PIL import Image
except:
    Image = None


ALLOWED_TYPES = [".pdf", ".docx", ".png", ".jpg", ".jpeg"]
MAX_SIZE_MB = 10


# -----------------------------
# VALIDATE FILE (IMPROVED)
# -----------------------------
def validate_file(file_path):
    logs = []
    errors = []
    warnings = []

    file_name = os.path.basename(file_path)
    file_ext = os.path.splitext(file_name)[1].lower()
    file_size = os.path.getsize(file_path) / (1024 * 1024)

    text = ""

    # -----------------------------
    # DQ-001 File Type
    # -----------------------------
    if file_ext not in ALLOWED_TYPES:
        logs.append(("DQ-001", "File Type Check", "FAIL", "Invalid file type"))
        errors.append("Invalid file type")
    else:
        logs.append(("DQ-001", "File Type Check", "PASS", "OK"))

    # -----------------------------
    # DQ-002 File Size
    # -----------------------------
    if file_size > MAX_SIZE_MB:
        logs.append(("DQ-002", "File Size Check", "FAIL", "File too large"))
        errors.append("File too large")
    else:
        logs.append(("DQ-002", "File Size Check", "PASS", "OK"))

    # -----------------------------
    # DQ-003 Readability + Extraction
    # -----------------------------
    try:
        if file_ext == ".pdf":
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "")
            logs.append(("DQ-003", "PDF Readability", "PASS", "Readable"))

        elif file_ext == ".docx" and docx:
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text
            logs.append(("DQ-003", "DOCX Readability", "PASS", "Readable"))

        elif file_ext in [".png", ".jpg", ".jpeg"] and Image:
            img = Image.open(file_path)
            img.verify()  # check corruption
            logs.append(("DQ-003", "Image Readability", "PASS", "Readable"))

        else:
            logs.append(("DQ-003", "Readability", "WARNING", "Skipped"))

    except Exception as e:
        logs.append(("DQ-003", "Readability", "FAIL", str(e)))
        errors.append("File not readable")

    # -----------------------------
    # DQ-005 Text Extraction Check
    # -----------------------------
    if file_ext in [".pdf", ".docx"]:
        if len(text.strip()) == 0:
            logs.append(("DQ-005", "Text Extraction", "FAIL", "No text found"))
            errors.append("No text found")
        else:
            logs.append(("DQ-005", "Text Extraction", "PASS", "OK"))
    else:
        logs.append(("DQ-005", "Text Extraction", "WARNING", "Not applicable"))

    # -----------------------------
    # DQ-006 Minimum Content
    # -----------------------------
    if file_ext in [".pdf", ".docx"]:
        #if len(text) < 200:
        if len(text.strip()) < 20:
            logs.append(("DQ-006", "Minimum Content", "FAIL", "Too little content"))
            errors.append("Too little content")
        else:
            logs.append(("DQ-006", "Minimum Content", "PASS", "OK"))
    else:
        logs.append(("DQ-006", "Minimum Content", "WARNING", "Not applicable"))

    # -----------------------------
    # DQ-007 Noise Check
    # -----------------------------
    if file_ext in [".pdf", ".docx"]:
        clean_text = text.strip().replace(" ", "")
        if len(clean_text) < 50:
            logs.append(("DQ-007", "Noise Check", "FAIL", "Too noisy"))
            errors.append("Too noisy")
        else:
            logs.append(("DQ-007", "Noise Check", "PASS", "OK"))
    else:
        logs.append(("DQ-007", "Noise Check", "WARNING", "Not applicable"))

    # -----------------------------
    # DQ-008 Image Quality Check
    # -----------------------------
    if file_ext in [".png", ".jpg", ".jpeg"] and Image:
        try:
            img = Image.open(file_path)
            width, height = img.size

            if width < 300 or height < 300:
                logs.append(("DQ-008", "Image Quality", "WARNING", "Low resolution"))
                warnings.append("Low resolution")
            else:
                logs.append(("DQ-008", "Image Quality", "PASS", "Good quality"))

        except Exception as e:
            logs.append(("DQ-008", "Image Quality", "FAIL", str(e)))
            errors.append("Image corrupted")
    else:
        logs.append(("DQ-008", "Image Quality", "WARNING", "Not applicable"))

    # -----------------------------
    # FINAL DECISION (DQ-009, DQ-010)
    # -----------------------------
    if len(errors) > 0:
        status = "INVALID"
        reason = ", ".join(errors)
    else:
        status = "VALID"
        reason = "All checks passed"

    return status, reason, logs


# -----------------------------
# MOVE FILE
# -----------------------------
def move_file(file_path, status):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)

    if status == "VALID":
        target_folder = os.path.join(project_root, "frontend", "input","success")
    else:
        target_folder = os.path.join(project_root, "frontend", "input", "failed")

    os.makedirs(target_folder, exist_ok=True)

    file_name = os.path.basename(file_path)
    name, ext = os.path.splitext(file_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    new_file_name = f"{name}_{timestamp}{ext}"
    new_path = os.path.join(target_folder, new_file_name)

    shutil.move(file_path, new_path)

    return new_path

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "INVALID",
            "reason": "No file path provided"
        }))
        sys.exit(1)

    file_path = sys.argv[1]

    status, reason, logs = validate_file(file_path)
    new_path = move_file(file_path, status)

    print(json.dumps({
        "status": status,
        "reason": reason,
        "saved_to": new_path
    }))