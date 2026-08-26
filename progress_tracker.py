import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "progress.db"
ROLLING_WINDOW = 10
WEAK_TOPIC_THRESHOLD = 60


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        # Create table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                score REAL,
                difficulty TEXT,
                question_type TEXT,
                timestamp DATETIME
            )
        """)
        
        # Add attempt_id column if missing
        try:
            conn.execute("ALTER TABLE attempts ADD COLUMN attempt_id TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists



def get_topic_mastery(topic):
    """Average score over the most recent ROLLING_WINDOW questions."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT score
            FROM attempts
            WHERE topic = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (topic, ROLLING_WINDOW),
        ).fetchall()

    if not rows:
        return None

    scores = [float(row[0]) for row in rows]
    return round(sum(scores) / len(scores), 1)


def get_topic_attempt_history(topic, limit=20):
    """
    Return one averaged score per quiz *submission* (not per question) for
    a topic, oldest first. All question rows written by a single call to
    record_quiz_results() share the same timestamp, so grouping by
    timestamp reconstructs one bar per attempt.
    """
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT timestamp, AVG(score)
            FROM attempts
            WHERE topic = ?
            GROUP BY timestamp
            ORDER BY timestamp ASC
            """,
            (topic,),
        ).fetchall()

    history = [
        {"timestamp": timestamp, "score": round(avg_score, 1)}
        for timestamp, avg_score in rows
    ]

    if limit:
        history = history[-limit:]

    return history


def get_recommended_difficulty(topic):
    """Choose difficulty from current topic mastery."""
    mastery = get_topic_mastery(topic)

    if mastery is None:
        return "medium"

    if mastery < 50:
        return "easy"

    if mastery < 80:
        return "medium"

    return "hard"


def get_all_topics_summary():
    """Return one summary dictionary per attempted topic."""
    with sqlite3.connect(DB_PATH) as conn:
        topics = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT topic FROM attempts"
            ).fetchall()
        ]

        summary = []

        for topic in topics:
            # Count UNIQUE quiz runs (attempt_id) instead of total rows
            count = conn.execute(
                "SELECT COUNT(DISTINCT attempt_id) FROM attempts WHERE topic = ?",
                (topic,),
            ).fetchone()[0]

            mastery = get_topic_mastery(topic)

            summary.append(
                {
                    "topic": topic,
                    "mastery": mastery,
                    "attempts": count,
                }
            )

        return summary


def get_topic_attempt_history(topic):
    """Return historical scores grouped by quiz run (attempt_id)."""
    with sqlite3.connect(DB_PATH) as conn:
        # Group by attempt_id to get the average score for each full quiz attempt
        rows = conn.execute(
            """
            SELECT attempt_id, AVG(score) as average_score, MIN(timestamp) as ts
            FROM attempts
            WHERE topic = ?
            GROUP BY attempt_id
            ORDER BY ts ASC
            """,
            (topic,),
        ).fetchall()

        return [{"score": row[1]} for row in rows]
    
def get_weak_topics(threshold=WEAK_TOPIC_THRESHOLD):
    return [
        topic
        for topic in get_all_topics_summary()
        if topic["mastery"] is not None and topic["mastery"] < threshold
    ]


if __name__ == "__main__":
    init_db()
    print("Progress database initialized.")