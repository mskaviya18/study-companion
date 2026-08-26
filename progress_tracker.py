"""
progress_tracker.py

Stores every quiz attempt in a local SQLite database, computes a rolling
mastery score per topic, and uses that score to recommend the difficulty
for the next quiz on that topic. This is the feedback loop from the
architecture diagram: tracked performance feeds back into what gets
generated next.

Run directly to test the full pipeline end-to-end (generate -> take quiz
-> evaluate -> record -> see mastery update):
    python progress_tracker.py
"""

import sqlite3
from datetime import datetime, timezone

from content_generator import generate_content
from quiz_generator import generate_quiz
from evaluator import evaluate_quiz, print_results

DB_PATH = "progress.db"
ROLLING_WINDOW = 10          # how many recent attempts count toward mastery
WEAK_TOPIC_THRESHOLD = 60    # mastery below this flags a topic as weak


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            question_type TEXT NOT NULL,   -- 'mcq' or 'short_answer'
            score REAL NOT NULL,           -- 0-100, per question
            difficulty TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def record_quiz_results(topic, results, difficulty):
    """Insert one row per question from an evaluator.py results dict."""
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc).isoformat()

    for r in results["mcq"]:
        score = 100 if r["correct"] else 0
        conn.execute(
            "INSERT INTO attempts (topic, question_type, score, difficulty, timestamp) VALUES (?, ?, ?, ?, ?)",
            (topic, "mcq", score, difficulty, now),
        )
    for r in results["short_answer"]:
        conn.execute(
            "INSERT INTO attempts (topic, question_type, score, difficulty, timestamp) VALUES (?, ?, ?, ?, ?)",
            (topic, "short_answer", r["score"], difficulty, now),
        )
    conn.commit()
    conn.close()


def get_topic_mastery(topic):
    """Average score over the most recent ROLLING_WINDOW attempts for this topic."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT score FROM attempts WHERE topic = ? ORDER BY timestamp DESC LIMIT ?",
        (topic, ROLLING_WINDOW),
    ).fetchall()
    conn.close()
    if not rows:
        return None  # no attempts yet
    scores = [r[0] for r in rows]
    return round(sum(scores) / len(scores), 1)


def get_recommended_difficulty(topic):
    """First attempt on a topic defaults to medium; afterward, mastery drives difficulty."""
    mastery = get_topic_mastery(topic)
    if mastery is None:
        return "medium"
    if mastery < 50:
        return "easy"
    elif mastery < 80:
        return "medium"
    else:
        return "hard"


def get_all_topics_summary():
    """One row per topic attempted so far, with mastery and attempt count."""
    conn = sqlite3.connect(DB_PATH)
    topics = [row[0] for row in conn.execute("SELECT DISTINCT topic FROM attempts")]
    conn.close()

    summary = []
    for topic in topics:
        mastery = get_topic_mastery(topic)
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute(
            "SELECT COUNT(DISTINCT timestamp) FROM attempts WHERE topic = ?", (topic,)
        ).fetchone()[0]
        conn.close()
        summary.append({"topic": topic, "mastery": mastery, "attempts": count})
    return sorted(summary, key=lambda x: x["mastery"])


def get_mastery_timeline():
    """
    Returns one row per quiz session (all questions submitted together share
    a timestamp) across every topic: {topic, timestamp (datetime), score}.
    'score' is that session's average across its questions. Sorted
    chronologically -- this is the raw series a chart plots directly.
    """
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT topic, timestamp, AVG(score) as session_score
        FROM attempts
        GROUP BY topic, timestamp
        ORDER BY timestamp ASC
    """).fetchall()
    conn.close()

    timeline = []
    for topic, timestamp, session_score in rows:
        timeline.append({
            "topic": topic,
            "timestamp": datetime.fromisoformat(timestamp),
            "score": round(session_score, 1),
        })
    return timeline


def get_weak_topics(threshold=WEAK_TOPIC_THRESHOLD):
    return [t for t in get_all_topics_summary() if t["mastery"] is not None and t["mastery"] < threshold]


def reset_progress(topic=None):
    """Delete all attempt history, or just for one topic if specified.
    Useful for demos/testing without needing to delete the .db file by hand."""
    conn = sqlite3.connect(DB_PATH)
    if topic:
        conn.execute("DELETE FROM attempts WHERE topic = ?", (topic,))
    else:
        conn.execute("DELETE FROM attempts")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()

    topic = input("Enter a syllabus topic: ")
    difficulty = get_recommended_difficulty(topic)
    print(f"Recommended difficulty for '{topic}': {difficulty} "
          f"(based on mastery: {get_topic_mastery(topic)})")

    print("Generating notes...")
    notes, _ = generate_content(topic)
    print("Generating quiz...")
    quiz = generate_quiz(topic, notes, difficulty=difficulty)

    mcq_answers = []
    print("\n--- Answer the multiple-choice questions ---")
    for i, q in enumerate(quiz["mcq"], 1):
        print(f"\nQ{i}. {q['question']}")
        for j, opt in enumerate(q["options"]):
            print(f"   {chr(65+j)}. {opt}")
        choice = input("Your answer (A/B/C/D): ").strip().upper()
        mcq_answers.append(ord(choice) - ord("A"))

    short_answers = []
    print("\n--- Answer the short-answer questions ---")
    for i, q in enumerate(quiz["short_answer"], 1):
        print(f"\nQ{i}. {q['question']}")
        answer = input("Your answer: ")
        short_answers.append(answer)

    print("\nGrading...")
    results = evaluate_quiz(quiz, mcq_answers, short_answers)
    print_results(results)

    record_quiz_results(topic, results, difficulty)
    print(f"\nUpdated mastery for '{topic}': {get_topic_mastery(topic)}")

    weak = get_weak_topics()
    if weak:
        print("\nTopics that could use more practice:")
        for t in weak:
            print(f"   {t['topic']}: {t['mastery']}/100 ({t['attempts']} attempts)")