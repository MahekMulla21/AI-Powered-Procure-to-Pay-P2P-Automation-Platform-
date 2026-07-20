from MSA_processing.MSA_chunking import split_text

print("\n📦 Splitting text into chunks...")
chunks = split_text(text)

all_data = []

for i, chunk in enumerate(chunks):
    print(f"\n🔹 Processing chunk {i+1}/{len(chunks)}")

    raw_response = extract_fields(chunk)
    data = clean_json(raw_response)

    if data:
        all_data.append(data)

# Merge results
final_data = {}
for d in all_data:
    for key, value in d.items():
        if value and key not in final_data:
            final_data[key] = value

data = validate(final_data)