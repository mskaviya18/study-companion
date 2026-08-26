"""
quiz_generator.py

Takes the study notes produced by content_generator.py and generates a
quiz: a mix of multiple-choice questions (auto-scorable) and short-answer
questions (graded later by evaluator.py using an LLM).

The model is asked to return strict JSON so the rest of the pipeline
(evaluator, progress tracker, UI) can work with structured data instead
of parsing free-form text. Occasionally a model wraps JSON in markdown
fences or adds stray text despite instructions -- this module cleans that
up and retries once before giving up.

Run directly to test:
    python quiz_generator.py
"""

import json
import re

from content_generator import generate_content
from llm_utils import generate_text

MAX_ATTEMPTS = 2


def build_quiz_prompt(topic, notes, num_mcq, num_short, difficulty):
    return f"""You are a quiz generator for a student studying "{topic}".

Base every question strictly on the study notes below. Do not introduce
facts that aren't in the notes.

Study notes:
{notes}

Generate:
- {num_mcq} multiple-choice questions at {difficulty} difficulty, each with
  exactly 4 options and exactly one correct option.
- {num_short} short-answer questions at {difficulty} difficulty, each with
  a list of 2-4 key points a correct answer should mention.

Return ONLY valid JSON, no markdown fences, no extra text, in this exact
structure:

{{
  "mcq": [
    {{
      "question": "...",
      "options": ["...", "...", "...", "..."],
      "correct_index": 0,
      "explanation": "..."
    }}
  ],
  "short_answer": [
    {{
      "question": "...",
      "key_points": ["...", "..."]
    }}
  ]
}}
"""


def _strip_code_fences(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()


def _validate_quiz_shape(quiz):
    """Basic structural check so a malformed-but-valid-JSON response gets caught early."""
    if "mcq" not in quiz or "short_answer" not in quiz:
        raise ValueError("Missing 'mcq' or 'short_answer' keys")
    for q in quiz["mcq"]:
        if len(q.get("options", [])) != 4 or "correct_index" not in q:
            raise ValueError("Malformed MCQ entry")
    for q in quiz["short_answer"]:
        if not q.get("key_points"):
            raise ValueError("Malformed short-answer entry")


def generate_quiz(topic, notes, num_mcq=3, num_short=2, difficulty="medium"):
    prompt = build_quiz_prompt(topic, notes, num_mcq, num_short, difficulty)

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = _strip_code_fences(generate_text(prompt))
            quiz = json.loads(raw)
            _validate_quiz_shape(quiz)
            return quiz
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            continue
        except RuntimeError:
            raise  # propagate API-level failures (rate limit, auth, etc.) immediately

    raise RuntimeError(
        f"Could not generate a valid quiz after {MAX_ATTEMPTS} attempts ({last_error}). Try again."
    )


def print_quiz(quiz):
    print("\n--- Multiple Choice ---")
    for i, q in enumerate(quiz.get("mcq", []), 1):
        print(f"\nQ{i}. {q['question']}")
        for j, opt in enumerate(q["options"]):
            print(f"   {chr(65+j)}. {opt}")

    print("\n--- Short Answer ---")
    for i, q in enumerate(quiz.get("short_answer", []), 1):
        print(f"\nQ{i}. {q['question']}")


if __name__ == "__main__":
    topic = input("Enter a syllabus topic: ")
    try:
        print("Generating notes...")
        notes, sources = generate_content(topic)

        print("Generating quiz from those notes...")
        quiz = generate_quiz(topic, notes)

        print_quiz(quiz)
        print("\n(Full quiz JSON has answers/explanations for grading in evaluator.py)")
    except Exception as e:
        print(f"Error: {e}")