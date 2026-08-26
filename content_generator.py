from llm_utils import generate_text
from rag_utils import retrieve_context

TOP_K = 4


def build_prompt_with_context(topic, chunks):
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
- Use clear headings and bullet points.
- Keep the notes exam-focused and concise.
"""


def build_prompt_fallback(topic):
    return f"""You are an expert AI study companion.

Generate comprehensive, well-structured study notes for a student preparing for exams on the topic: "{topic}"

Instructions:
- Include a clear short definition.
- Explain core concepts simply and thoroughly.
- Provide practical examples and code snippets where relevant.
- List key properties, time/space complexities, or important rules if applicable.
- Use clear markdown headings, bold text, and bullet points.
- Keep the notes exam-focused, structured, and easy to memorize.
"""


def generate_content(topic):
    chunks, sources = retrieve_context(topic, top_k=TOP_K)

    # If no local reference files are found in data/, fall back to pure AI generation
    if not chunks:
        prompt = build_prompt_fallback(topic)
        notes = generate_text(prompt, temperature=0.3, max_tokens=3000)
        return notes.strip(), ["AI General Knowledge"]

    prompt = build_prompt_with_context(topic, chunks)
    notes = generate_text(prompt, temperature=0.2, max_tokens=3000)

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
        build_prompt_with_context(topic, [truncated]),
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