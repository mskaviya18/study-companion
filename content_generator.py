"""
content_generator.py

Two ways to generate study notes for a topic:

1. generate_grounded_content(topic) -- RAG mode. Retrieves the most
   relevant chunks from whatever reference material has been uploaded
   and indexed, and asks the LLM to write notes using ONLY that material.
   Raises NoReferenceMaterialError if nothing relevant is indexed.

2. generate_general_content(topic) -- no-upload mode. Skips retrieval
   entirely and asks the LLM to write notes from its own general
   knowledge. No source material required, but no grounding guarantee
   either -- this is plain LLM generation, included so the app still
   works for topics the user hasn't uploaded anything for.

Run directly to test grounded mode:
    python content_generator.py
"""

from rag_utils import get_collection
from llm_utils import generate_text

TOP_K = 4  # how many chunks to retrieve per query


class NoReferenceMaterialError(Exception):
    """Raised when there's nothing indexed yet, or nothing relevant to the topic."""
    pass


def retrieve_context(topic, top_k=TOP_K):
    """Query the vector store with the topic text directly -- Chroma embeds
    the query locally using the same model it used to embed the documents.
    Returns ([], []) if the store is empty rather than raising, so callers can
    decide how to handle 'no material yet' as a normal case, not a crash."""
    collection = get_collection()
    if collection.count() == 0:
        return [], []

    results = collection.query(query_texts=[topic], n_results=min(top_k, collection.count()))

    chunks = results["documents"][0]
    sources = [meta["source"] for meta in results["metadatas"][0]]
    return chunks, sources


def _build_grounded_prompt(topic, chunks):
    context = "\n\n---\n\n".join(chunks)
    return f"""You are a study-notes generator for a student preparing for exams.

Using ONLY the reference material below, write clear, structured study notes
on the topic: "{topic}"

Reference material:
{context}

Instructions:
- Include: a short definition, key concepts explained simply, at least one
  example, and any relevant formulas or complexity/rules mentioned in the text.
- If the reference material does not fully cover the topic, say so explicitly
  rather than filling gaps with outside knowledge.
- Use clear headings and bullet points. Keep it exam-focused, not a full essay.
"""


def _build_general_prompt(topic):
    return f"""You are a study-notes generator for a student preparing for exams.

Write clear, structured study notes on the topic: "{topic}"

Instructions:
- Include: a short definition, key concepts explained simply, at least one
  worked example, and any relevant formulas, rules, or complexity details
  that are standard/well-established for this topic.
- Use clear headings and bullet points. Keep it exam-focused, not a full essay.
- Stick to well-established, standard facts about this topic. If the topic
  is too vague or ambiguous to address confidently, say so rather than
  guessing.
"""


def generate_grounded_content(topic):
    """RAG mode. Raises NoReferenceMaterialError if nothing relevant is indexed."""
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty.")

    chunks, sources = retrieve_context(topic)
    if not chunks:
        raise NoReferenceMaterialError(
            "No reference material is indexed yet, or nothing matched this topic. "
            "Upload a .txt or .pdf file, or switch to general-knowledge mode."
        )

    prompt = _build_grounded_prompt(topic, chunks)
    text = generate_text(prompt)
    return text, sorted(set(sources))


def generate_general_content(topic):
    """No-upload mode. Always returns notes (assuming the API call succeeds);
    sources list is empty since nothing was retrieved."""
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty.")

    prompt = _build_general_prompt(topic)
    text = generate_text(prompt)
    return text, []


# Backwards-compatible alias: existing code (quiz_generator, evaluator test
# blocks) calls generate_content() expecting grounded behavior.
def generate_content(topic):
    return generate_grounded_content(topic)


if __name__ == "__main__":
    topic = input("Enter a syllabus topic: ")
    mode = input("Mode - (g)rounded or (n)o-upload? [g/n]: ").strip().lower()
    try:
        if mode == "n":
            notes, sources = generate_general_content(topic)
        else:
            notes, sources = generate_grounded_content(topic)
        print("\n" + "=" * 60)
        print(notes)
        print("=" * 60)
        if sources:
            print(f"\nGrounded in: {', '.join(sources)}")
        else:
            print("\n(Generated from general knowledge, not grounded in uploaded material)")
    except (NoReferenceMaterialError, ValueError, RuntimeError) as e:
        print(f"Error: {e}")