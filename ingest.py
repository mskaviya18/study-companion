"""
ingest.py

Batch-indexes every .txt and .pdf file in data/ into the persistent Chroma
vector store. Embeddings are generated locally (see rag_utils.py) --
no API key needed for this step. Run this once whenever you add new
reference material to data/:
    python ingest.py

For adding material through the app itself (no terminal needed), use the
"Add reference material" uploader inside app.py instead -- both paths use
the same underlying logic in rag_utils.py.
"""

import os
import glob

from rag_utils import add_document_to_store, extract_text_from_pdf

DATA_DIR = "data"


def main():
    txt_files = glob.glob(os.path.join(DATA_DIR, "*.txt"))
    pdf_files = glob.glob(os.path.join(DATA_DIR, "*.pdf"))
    all_files = txt_files + pdf_files

    if not all_files:
        print(f"No .txt or .pdf files found in {DATA_DIR}/. Add reference material and rerun.")
        return

    for file_path in all_files:
        source_name = os.path.basename(file_path)
        try:
            if file_path.endswith(".pdf"):
                with open(file_path, "rb") as f:
                    text = extract_text_from_pdf(f)
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