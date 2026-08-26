from pathlib import Path
import docx
from PIL import Image
import pytesseract
from pypdf import PdfReader

# Streamlit Cloud's system sqlite3 is older than the 3.35.0 that chromadb
# requires. Swap in the pysqlite3-binary wheel before chromadb imports sqlite3.
try:
    __import__("pysqlite3")
    import sys

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import chromadb

STORE_DIR = "chroma_store"
COLLECTION_NAME = "study_material"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def get_collection():
    """Return the persistent Chroma collection using its default local embedding."""
    client = chromadb.PersistentClient(path=STORE_DIR)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size.")

    chunks = []
    step = chunk_size - overlap

    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def extract_text_from_pdf(file_obj):
    """Extract text from a PDF file-like object."""
    reader = PdfReader(file_obj)
    pages_text = []

    for page in reader.pages:
        pages_text.append(page.extract_text() or "")

    return "\n".join(pages_text)


def extract_text_from_docx(file_obj):
    """Extract text from a DOCX file-like object."""
    doc = docx.Document(file_obj)
    paragraphs_text = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs_text)


def extract_text_from_image(file_obj):
    """Extract text from an image file-like object using OCR."""
    image = Image.open(file_obj)
    return pytesseract.image_to_string(image)


def add_document_to_store(source_name, text):
    """Chunk and upsert one document into the persistent Chroma collection."""
    source_name = Path(str(source_name)).name
    chunks = chunk_text(text)

    if not chunks:
        return 0

    collection = get_collection()

    # Remove stale chunks if the same source is re-added with fewer chunks.
    existing = collection.get(where={"source": source_name})
    old_ids = existing.get("ids", []) if existing else []
    if old_ids:
        collection.delete(ids=old_ids)

    ids = [f"{source_name}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source_name} for _ in chunks]

    collection.add(
        ids=ids,
        documents=chunks,
        metadatas=metadatas,
    )

    return len(chunks)


def retrieve_context(query, top_k=4):
    """Retrieve the most relevant indexed chunks for a query."""
    collection = get_collection()

    if collection.count() == 0:
        return [], []

    result = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]

    sources = [
        metadata.get("source", "Unknown") for metadata in metadatas if metadata
    ]

    return documents, sources


def list_sources():
    """Return distinct source filenames currently indexed."""
    collection = get_collection()

    if collection.count() == 0:
        return []

    metadata = collection.get().get("metadatas", [])
    return sorted(
        {item.get("source") for item in metadata if item and item.get("source")}
    )