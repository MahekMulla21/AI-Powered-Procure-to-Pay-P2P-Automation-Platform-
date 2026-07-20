# NOTE: This file appears to be a leftover from Invoice to PO conversion
# and is not currently used in the pipeline. The chunking functionality
# is handled differently in the current PO processing pipeline.
# Uncomment and fix imports if needed in the future.

# from PO_processing.po_chunking import split_text
# from PO_processing.po_cleaner import clean_json
# from PO_llm.po_extractor import extract_fields
# from PO_processing.po_validator import validate
# from PO_processing.po_pdf_detector import text
#
# 
# print("\n Splitting text into chunks...")
# chunks = split_text(text)
#
# all_data = []
#
# for i, chunk in enumerate(chunks):
#     print(f"\n🔹 Processing chunk {i+1}/{len(chunks)}")
#
#     raw_response = extract_fields(chunk)
#     data = clean_json(raw_response)
#
#     if data:
#         all_data.append(data)
#
# # Merge results
# final_data = {}
# for d in all_data:
#     for key, value in d.items():
#         if value and key not in final_data:
#             final_data[key] = value
#
# data = validate(final_data)