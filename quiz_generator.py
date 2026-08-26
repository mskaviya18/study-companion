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
- Each MCQ must have exactly 4 options and exactly one correct option index (0 to 3).
- {num_short} short-answer questions at {difficulty} difficulty.
- Each short-answer question must have an "ideal_answer" and 2-4 key points.

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
      "ideal_answer": "...",
      "key_points": ["...", "..."]
    }}
  ]
}}
"""

def _extract_json(text):
    """Extracts raw JSON structure by locating outer curly braces, stripping thinking blocks,

    and handling invalid unescaped characters inside strings.
    """
    # Remove reasoning/thinking tags emitted by thinking models
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Find boundaries of the JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"Model did not return valid JSON. Raw output was:\n{cleaned}"
        )

    json_str = cleaned[start : end + 1]

    # Strip code block wrappers if left inside bounds
    json_str = re.sub(r"^```(?:json)?\s*", "", json_str, flags=re.IGNORECASE)
    json_str = re.sub(r"\s*```$", "", json_str)

    # Attempt standard parse first with strict=False to allow unescaped control chars (like newlines)
    try:
        return json.loads(json_str, strict=False)
    except json.JSONDecodeError:
        pass

    # If parsing fails, fix unescaped double quotes inside values (e.g. "code": "echo "hello"")
    def fix_unescaped_quotes(match):
        key_val = match.group(0)
        # Fix inner unescaped quotes inside string values
        return re.sub(r'(?<!\\)"', r'\"', key_val)

    # Sanitize and parse
    try:
        # Normalize newlines inside JSON strings
        sanitized = re.sub(r'(?<!\\)\n', r'\\n', json_str)
        return json.loads(sanitized, strict=False)
    except json.JSONDecodeError as err:
        raise ValueError(f"Model returned invalid JSON string syntax: {err}\n\nRaw string:\n{json_str}")


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
            f"Expected {num_short} short-answer questions, received {len(short_answer)}."
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


def generate_quiz(topic, notes, num_mcq=6, num_short=4, difficulty="medium", max_retries=2):
    prompt = build_quiz_prompt(
        topic,
        notes,
        num_mcq,
        num_short,
        difficulty,
    )

    last_error = None
    for attempt in range(max_retries):
        try:
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
        except (ValueError, json.JSONDecodeError) as err:
            last_error = err
            continue

    raise RuntimeError(f"Failed to generate a valid quiz after {max_retries} attempts: {last_error}")


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