# save_as: add_pdf_to_faiss.py

import os
import pickle
import requests
import faiss
import numpy as np

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

# ✅ YOUR PDF PATH
PDF_PATH = r"C:\Users\ws_htu769\Desktop\P2P\final_integerated_code_v2\backend\data\the_Policy_document.pdf"

# ✅ YOUR FAISS DB FOLDER
FAISS_FOLDER = r"faiss_db/output"

INDEX_FILE = os.path.join(FAISS_FOLDER, "global_faiss.index")
MAPPING_FILE = os.path.join(FAISS_FOLDER, "global_faiss_mapping.pkl")


# ─────────────────────────────────────────────
# LLM CONFIG
# ─────────────────────────────────────────────

MODEL_NAME = "llama3"
API = "sk-b2fec1202df44aec868c8eab5b767ba6"
URL = "http://10.1.1.219:8080/ollama/api/generate"


# ─────────────────────────────────────────────
# EMBEDDING MODEL
# ─────────────────────────────────────────────

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


# ─────────────────────────────────────────────
# LOAD FAISS INDEX
# ─────────────────────────────────────────────

if os.path.exists(INDEX_FILE):
    print("Loading existing FAISS index...")
    index = faiss.read_index(INDEX_FILE)
else:
    print("Creating new FAISS index...")
    dimension = 384
    index = faiss.IndexFlatL2(dimension)

# Load metadata mapping
if os.path.exists(MAPPING_FILE):
    with open(MAPPING_FILE, "rb") as f:
        metadata_store = pickle.load(f)
else:
    metadata_store = []


# ─────────────────────────────────────────────
# OPTIONAL CLEANING USING LLM
# ─────────────────────────────────────────────

def clean_text_with_llm(text):

    prompt = f"""
Clean and normalize the following OCR/document text.
Remove garbage characters and preserve meaning.

TEXT:
{text}
"""

    headers = {
        "Authorization": f"Bearer {API}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(
            URL,
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("response", text)

        else:
            print("LLM API Error:", response.text)
            return text

    except Exception as e:
        print("LLM Cleaning Failed:", e)
        return text


# ─────────────────────────────────────────────
# ADD PDF TO VECTOR DB
# ─────────────────────────────────────────────

def add_pdf_to_vector_db(pdf_path):

    if not os.path.exists(pdf_path):
        print("PDF not found")
        return

    print(f"\nProcessing PDF: {pdf_path}")

    # Load PDF
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    # Split text
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = splitter.split_documents(documents)

    print(f"Chunks created: {len(chunks)}")

    texts = []
    metadata = []

    for chunk in chunks:

        raw_text = chunk.page_content.strip()

        if not raw_text:
            continue

        # OPTIONAL LLM CLEANING
        cleaned_text = clean_text_with_llm(raw_text)

        texts.append(cleaned_text)

        metadata.append({
            "source_file": os.path.basename(pdf_path),
            "page": chunk.metadata.get("page", "N/A"),
            "content": cleaned_text
        })

    # Generate embeddings
    embeddings = embedding_model.encode(
        texts,
        convert_to_numpy=True
    ).astype("float32")

    # Store in FAISS
    index.add(embeddings)

    # Store metadata
    metadata_store.extend(metadata)

    print(f"Added {len(texts)} chunks into FAISS DB")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":

    add_pdf_to_vector_db(PDF_PATH)

    # Save FAISS
    faiss.write_index(index, INDEX_FILE)

    # Save metadata
    with open(MAPPING_FILE, "wb") as f:
        pickle.dump(metadata_store, f)

    print("\nFAISS DB updated successfully!")