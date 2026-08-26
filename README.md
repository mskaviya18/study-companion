# AI Study Companion — Module 1: Content Generator

## Setup (in VS Code terminal)

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

1. Copy `.env.example` to `.env`
2. Paste your Groq API key into `.env`:
   ```
   GROQ_API_KEY=your_actual_key_here
   ```

## Usage

1. Add your reference material as `.txt` files inside `data/`
   (a sample file on Binary Search Trees is already included so you can test immediately)
2. Build the vector index:
   ```bash
   python ingest.py
   ```
3. Generate grounded notes for a topic:
   ```bash
   python content_generator.py
   ```
   Then type a topic, e.g. `Binary Search Trees`

## How it works

- `ingest.py` splits your reference files into overlapping ~800-character
  chunks, embeds each chunk with Gemini's embedding model, and stores them
  in a local Chroma vector database (`chroma_store/`).
- `content_generator.py` embeds your topic query, retrieves the most
  similar chunks, and prompts Gemini to write notes using *only* that
  retrieved material — this is the RAG grounding step that keeps content
  accurate to your syllabus rather than the model's general knowledge.

## Next module

`quiz_generator.py` will take the notes produced here and generate MCQ +
short-answer questions from them.

## Setting up OCR for scanned images

Uploading `.png`/`.jpg`/`.jpeg` files (e.g. a photographed or scanned page)
uses OCR to extract text, via the `pytesseract` Python package. That
package is just a wrapper — it needs the actual **Tesseract OCR engine**
installed separately on your machine:

**Windows:**
1. Download the installer from the UB-Mannheim build: search "tesseract ocr windows installer UB-Mannheim" or go to `github.com/UB-Mannheim/tesseract/wiki`
2. Run the installer (default install path is usually `C:\Program Files\Tesseract-OCR`)
3. Add that folder to your system PATH, **or** add this line near the top of `rag_utils.py` pointing to your install location:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```

**Mac:** `brew install tesseract`

**Linux:** `sudo apt install tesseract-ocr`

Without Tesseract installed, uploading `.txt`, `.pdf`, and `.docx` files
still works fine — only image OCR needs this extra step. If it's missing,
the app shows a clear error explaining what to install rather than crashing.

**Note on Streamlit Cloud:** free hosting doesn't let you install system
packages like Tesseract, so OCR uploads won't work on the deployed version
unless you add a `packages.txt` file (containing the line `tesseract-ocr`)
to your repo root — Streamlit Cloud reads this file to install Linux
system packages during deployment.