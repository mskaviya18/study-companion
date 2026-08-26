"""
rag_utils.py

Shared helpers for turning raw text/PDF into chunks and storing them in
the Chroma vector store. Embeddings are generated locally by Chroma's
built-in model (all-MiniLM-L6-v2, runs on-device via onnxruntime) --
no API key or quota needed for this step, only for the generation calls
in llm_utils.py.
"""

import chromadb
from pypdf import PdfReader

STORE_DIR = "chroma_store"
COLLECTION_NAME = "study_material"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def get_collection():
    """Get the collection if it exists, or create an empty one. Never wipes data.
    No embedding_function is specified, so Chroma uses its default local model --
    the first call downloads a small (~80MB) model file, then it's fully offline."""
    client = chromadb.PersistentClient(path=STORE_DIR)
    return client.get_or_create_collection(COLLECTION_NAME)


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def extract_text_from_pdf(file_obj):
    """file_obj: a file-like object (works with Streamlit's UploadedFile or open())."""
    reader = PdfReader(file_obj)
    pages_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)
    return "\n".join(pages_text)


def add_document_to_store(source_name, text):
    """
    Chunk and add a single document to the persistent collection. Chroma
    embeds the chunks locally under the hood. Uses upsert-safe IDs
    (source_name + chunk index) so re-adding the same file overwrites its
    old chunks instead of duplicating them.
    Returns the number of chunks added.
    """
    chunks = chunk_text(text)
    if not chunks:
        return 0

    ids = [f"{source_name}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source_name} for _ in chunks]

    collection = get_collection()
    collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)


def list_sources():
    """Return the distinct source filenames currently indexed, for display in the UI."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    all_meta = collection.get()["metadatas"]
    return sorted(set(m["source"] for m in all_meta))


def delete_source(source_name):
    """Remove every chunk belonging to one indexed file. Returns the number of chunks removed."""
    collection = get_collection()
    matches = collection.get(where={"source": source_name})
    ids = matches["ids"]
    if ids:
        collection.delete(ids=ids)
    return len(ids)