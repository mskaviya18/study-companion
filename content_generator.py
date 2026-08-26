from llm_utils import generate_text
from rag_utils import retrieve_context


TOP_K = 4


def build_prompt(topic, chunks):
    context = "\n\n---\n\n".join(chunks)

    return f"""You are a study-notes generator for a student preparing for exams.

Using ONLY the reference material below, write clear, structured study notes
on the topic: "{topic}"

Reference material:
{context}

Instructions:
- Include a short definition.
- Explain the key concepts simply.
- Include at least one example if the reference material provides enough information.
- Include formulas, rules, or complexity information only when present in the reference.
- Do not invent facts that are absent from the reference material.
- If the reference material does not fully cover the topic, say so explicitly.
- Use clear headings and bullet points.
- Keep the notes exam-focused and concise.
"""


def generate_content(topic):
    chunks, sources = retrieve_context(topic, top_k=TOP_K)

    if not chunks:
        return (
            "No reference material found for this topic. "
            "Add .txt files to data/ and run ingest.py first.",
            [],
        )

    notes = generate_text(
        build_prompt(topic, chunks),
        temperature=0.2,
        max_tokens=3000,
    )

    return notes.strip(), sorted(set(sources))


MAX_UPLOAD_CHARS = 12000


def generate_content_from_text(topic, text, source_name="Uploaded document"):
    """
    Generate study notes directly from a user-uploaded document's text,
    bypassing the vector store entirely. Used by the "Upload document" mode.
    """
    text = (text or "").strip()

    if not text:
        return (
            "The uploaded document appears to be empty or unreadable.",
            [],
        )

    # Keep the prompt within a safe size; long documents are truncated.
    truncated = text[:MAX_UPLOAD_CHARS]

    notes = generate_text(
        build_prompt(topic, [truncated]),
        temperature=0.2,
        max_tokens=3000,
    )

    return notes.strip(), [source_name]


if __name__ == "__main__":
    topic = input("Enter a syllabus topic: ").strip()

    if not topic:
        raise SystemExit("Please enter a topic.")

    notes, sources = generate_content(topic)

    print("\n" + "=" * 60)
    print(notes)
    print("=" * 60)
    print(f"\nGrounded in: {', '.join(sources) if sources else 'None'}")