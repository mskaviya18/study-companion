"""
ingest.py

Batch-indexes every .txt, .pdf, .docx, and image (.png/.jpg/.jpeg, via OCR)
file in data/ into the persistent Chroma vector store. Embeddings are
generated locally (see rag_utils.py) -- no API key needed for this step.
Run this once whenever you add new reference material to data/:
    python ingest.py

For adding material through the app itself (no terminal needed), use the
"Add reference material" uploader inside app.py instead -- both paths use
the same underlying logic in rag_utils.py.
"""

import os
import glob

from rag_utils import (
    add_document_to_store, extract_text_from_pdf, extract_text_from_docx,
    extract_text_from_image,
)

DATA_DIR = "data"


def main():
    patterns = ["*.txt", "*.pdf", "*.docx", "*.png", "*.jpg", "*.jpeg"]
    all_files = []
    for pattern in patterns:
        all_files.extend(glob.glob(os.path.join(DATA_DIR, pattern)))

    if not all_files:
        print(f"No supported files found in {DATA_DIR}/. Add reference material and rerun.")
        return

    for file_path in all_files:
        source_name = os.path.basename(file_path)
        name_lower = source_name.lower()
        try:
            if name_lower.endswith(".pdf"):
                with open(file_path, "rb") as f:
                    text = extract_text_from_pdf(f)
            elif name_lower.endswith(".docx"):
                with open(file_path, "rb") as f:
                    text = extract_text_from_docx(f)
            elif name_lower.endswith((".png", ".jpg", ".jpeg")):
                with open(file_path, "rb") as f:
                    text = extract_text_from_image(f)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()

            if not text.strip():
                print(f"{source_name}: no extractable text, skipped")
                continue

            n_chunks = add_document_to_store(source_name, text)
            print(f"{source_name}: {n_chunks} chunks indexed")

        except Exception as e:
            print(f"{source_name}: failed to index ({e})")

    print("Done.")


if __name__ == "__main__":
    main()