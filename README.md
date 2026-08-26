# AI Study Companion — Module 1: Content Generator

## Setup (in VS Code terminal)

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

1. Copy `.env.example` to `.env`
2. Paste your Gemini API key into `.env`:
   ```
   GEMINI_API_KEY=your_actual_key_here
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
