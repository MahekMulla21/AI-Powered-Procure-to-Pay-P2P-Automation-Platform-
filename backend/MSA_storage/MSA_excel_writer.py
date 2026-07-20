import pandas as pd
import os
from MSA_config.MSA_settings import EXCEL_OUTPUT

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