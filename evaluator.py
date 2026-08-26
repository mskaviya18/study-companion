"""
evaluator.py

Scores a completed quiz (as produced by quiz_generator.py):
- MCQs are scored by direct comparison against correct_index.
- Short-answer responses are graded by an LLM, which checks the student's
  free-text answer against the expected key_points and returns a score
  plus a short explanation of what was right or missing.

This module also runs the quiz interactively end-to-end for testing:
    python evaluator.py
"""

import json
import re

from content_generator import generate_content
from quiz_generator import generate_quiz
from llm_utils import generate_text

MAX_ATTEMPTS = 2


def _strip_code_fences(text):
    text = text.strip()

    # Remove reasoning/thinking tags emitted by thinking models
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.strip()

    # Remove markdown code block fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def evaluate_mcq(question, selected_index):
    """Direct comparison -- no LLM call, no failure mode beyond a bad index."""
    correct = selected_index == question["correct_index"]
    return {
        "correct": correct,
        "correct_index": question["correct_index"],
        "correct_option": question["options"][question["correct_index"]],
        "explanation": question.get("explanation", ""),
    }


def evaluate_short_answer(question, student_answer):
    """LLM-graded: checks the free-text answer against expected key points.
    Retries once on a malformed response before falling back to a safe default
    so one bad grading call doesn't crash the whole results page."""
    key_points = question.get("key_points", [])
    ideal_answer = question.get("ideal_answer") or question.get("correct_answer", "")

    if not student_answer or not student_answer.strip():
        return {
            "score": 0,
            "covered_points": [],
            "missing_points": key_points,
            "feedback": "No answer was submitted for this question.",
            "ideal_answer": ideal_answer,
        }

    prompt = f"""You are grading a student's short answer against expected key points.

Question: {question['question']}
Expected key points: {json.dumps(key_points)}
Student's answer: "{student_answer}"

Score the answer from 0 to 100 based on how many key points it correctly
covers. Be fair to different phrasing that still conveys the same idea.

Return ONLY valid JSON, no markdown fences, in this exact structure:
{{
  "score": 0,
  "covered_points": ["..."],
  "missing_points": ["..."],
  "feedback": "one or two sentences of feedback for the student"
}}
"""
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = _strip_code_fences(generate_text(prompt))
            result = json.loads(raw)
            if "score" not in result:
                raise ValueError("Missing 'score' key")
            
            # Ensure ideal_answer is attached for app.py UI
            result["ideal_answer"] = ideal_answer
            return result
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            continue
        except RuntimeError:
            raise  # propagate API-level failures immediately

    # Fallback: don't crash the results page over a grading hiccup
    return {
        "score": 0,
        "covered_points": [],
        "missing_points": key_points,
        "feedback": f"Could not grade this automatically after {MAX_ATTEMPTS} attempts ({last_error}). Please review manually.",
        "ideal_answer": ideal_answer,
    }


def evaluate_quiz(quiz, mcq_answers, short_answers):
    """
    mcq_answers: list of selected option indices, same order as quiz['mcq']
    short_answers: list of free-text strings, same order as quiz['short_answer']
    Returns a results dict with per-question feedback and an overall score.
    """
    results = {"mcq": [], "short_answer": [], "overall_score": 0}
    total_points, earned_points = 0, 0

    for q, selected in zip(quiz.get("mcq", []), mcq_answers):
        r = evaluate_mcq(q, selected)
        results["mcq"].append({"question": q["question"], **r})
        total_points += 1
        earned_points += 1 if r["correct"] else 0

    for q, answer in zip(quiz.get("short_answer", []), short_answers):
        r = evaluate_short_answer(q, answer)
        results["short_answer"].append({"question": q["question"], **r})
        total_points += 1
        earned_points += r["score"] / 100

    if total_points > 0:
        results["overall_score"] = round(100 * earned_points / total_points, 1)
    return results


def print_results(results):
    print("\n--- MCQ results ---")
    for r in results["mcq"]:
        mark = "correct" if r["correct"] else "incorrect"
        print(f"\n[{mark}] {r['question']}")
        if not r["correct"]:
            print(f"   Correct answer: {r['correct_option']}")
        if r["explanation"]:
            print(f"   Why: {r['explanation']}")

    print("\n--- Short answer results ---")
    for r in results["short_answer"]:
        print(f"\n{r['question']}")
        print(f"   Score: {r['score']}/100")
        print(f"   Feedback: {r['feedback']}")
        if r["missing_points"]:
            print(f"   You missed: {', '.join(r['missing_points'])}")

    print(f"\n=== Overall score: {results['overall_score']}/100 ===")


if __name__ == "__main__":
    topic = input("Enter a syllabus topic: ")
    try:
        print("Generating notes...")
        notes, _ = generate_content(topic)
        print("Generating quiz...")
        quiz = generate_quiz(topic, notes)

        mcq_answers = []
        print("\n--- Answer the multiple-choice questions ---")
        for i, q in enumerate(quiz.get("mcq", []), 1):
            print(f"\nQ{i}. {q['question']}")
            for j, opt in enumerate(q["options"]):
                print(f"   {chr(65+j)}. {opt}")
            choice = input("Your answer (A/B/C/D): ").strip().upper()
            mcq_answers.append(ord(choice) - ord("A"))

        short_answers = []
        print("\n--- Answer the short-answer questions ---")
        for i, q in enumerate(quiz.get("short_answer", []), 1):
            print(f"\nQ{i}. {q['question']}")
            answer = input("Your answer: ")
            short_answers.append(answer)

        print("\nGrading...")
        results = evaluate_quiz(quiz, mcq_answers, short_answers)
        print_results(results)
    except Exception as e:
        print(f"Error: {e}")