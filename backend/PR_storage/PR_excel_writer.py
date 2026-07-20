import pandas as pd
import os
from PR_config.PR_settings import EXCEL_OUTPUT

def save_to_excel(data):
    structured = data.get("structured", {})

    df = pd.DataFrame([structured])

    if os.path.exists(EXCEL_OUTPUT):
        try:
            os.remove(EXCEL_OUTPUT)
        except:
            print("⚠️ Close Excel file before writing!")
            return

    df.to_excel(EXCEL_OUTPUT, index=False)