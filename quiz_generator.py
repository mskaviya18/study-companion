import json
import re

from llm_utils import generate_text


def build_quiz_prompt(topic, notes, num_mcq, num_short, difficulty):
    return f"""You are a quiz generator for a student studying "{topic}".

Base every question strictly on the study notes below. Do not introduce facts
that are not present in the notes.

Study notes:
{notes}

Generate:
- {num_mcq} multiple-choice questions at {difficulty} difficulty.
- Each MCQ must have exactly 4 options and exactly one correct option.
- {num_short} short-answer questions at {difficulty} difficulty.
- Each short-answer question must have 2-4 key points.

Return ONLY valid JSON, with no markdown fences and no extra text.

Required structure:
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
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json(text):
    cleaned = _strip_code_fences(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise ValueError(
                f"Model did not return valid JSON. Raw output was:\n{cleaned}"
            )

        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Model did not return valid JSON. Raw output was:\n{cleaned}"
            ) from exc


def _validate_quiz(quiz, num_mcq, num_short):
    if not isinstance(quiz, dict):
        raise ValueError("Quiz response must be a JSON object.")

    mcq = quiz.get("mcq")
    short_answer = quiz.get("short_answer")

    if not isinstance(mcq, list) or not isinstance(short_answer, list):
        raise ValueError("Quiz JSON must contain mcq and short_answer arrays.")

    if len(mcq) != num_mcq:
        raise ValueError(f"Expected {num_mcq} MCQs, received {len(mcq)}.")

    if len(short_answer) != num_short:
        raise ValueError(
            f"Expected {num_short} short-answer questions, "
            f"received {len(short_answer)}."
        )

    for index, question in enumerate(mcq, 1):
        if not isinstance(question, dict):
            raise ValueError(f"MCQ {index} is not an object.")

        options = question.get("options")
        correct_index = question.get("correct_index")

        if not isinstance(question.get("question"), str):
            raise ValueError(f"MCQ {index} has no valid question.")

        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(f"MCQ {index} must contain exactly 4 options.")

        if (
            not isinstance(correct_index, int)
            or correct_index < 0
            or correct_index >= 4
        ):
            raise ValueError(f"MCQ {index} has an invalid correct_index.")

        if not all(isinstance(option, str) and option.strip() for option in options):
            raise ValueError(f"MCQ {index} contains an invalid option.")

    for index, question in enumerate(short_answer, 1):
        if not isinstance(question, dict):
            raise ValueError(f"Short-answer question {index} is not an object.")

        key_points = question.get("key_points")

        if not isinstance(question.get("question"), str):
            raise ValueError(f"Short-answer question {index} has no valid question.")

        if (
            not isinstance(key_points, list)
            or not 2 <= len(key_points) <= 4
            or not all(isinstance(point, str) for point in key_points)
        ):
            raise ValueError(
                f"Short-answer question {index} must contain 2-4 key points."
            )

    return quiz


def generate_quiz(topic, notes, num_mcq=6, num_short=4, difficulty="medium"):
    prompt = build_quiz_prompt(
        topic,
        notes,
        num_mcq,
        num_short,
        difficulty,
    )

    raw = generate_text(
        prompt,
        temperature=0.2,
        max_tokens=3000,
    )

    quiz = _extract_json(raw)

    return _validate_quiz(
        quiz,
        num_mcq=num_mcq,
        num_short=num_short,
    )


def print_quiz(quiz):
    print("\n--- Multiple Choice ---")

    for i, question in enumerate(quiz.get("mcq", []), 1):
        print(f"\nQ{i}. {question['question']}")
        for j, option in enumerate(question["options"]):
            print(f"   {chr(65 + j)}. {option}")

    print("\n--- Short Answer ---")

    for i, question in enumerate(quiz.get("short_answer", []), 1):
        print(f"\nQ{i}. {question['question']}")


if __name__ == "__main__":
    topic = input("Enter a syllabus topic: ").strip()

    if not topic:
        raise SystemExit("Please enter a topic.")

    notes = input("Paste the study notes: ").strip()

    if not notes:
        raise SystemExit("Please provide study notes.")

    quiz = generate_quiz(topic, notes)

    print_quiz(quiz)
    print("\nQuiz generated successfully.")