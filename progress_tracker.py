import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "progress.db"
ROLLING_WINDOW = 10
WEAK_TOPIC_THRESHOLD = 60


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
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
        try:
            conn.execute("ALTER TABLE attempts ADD COLUMN attempt_id TEXT")
        except sqlite3.OperationalError:
            pass


def record_quiz_results(topic, results, difficulty):
    attempt_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        for item in results.get("mcq", []):
            conn.execute(
                """
                INSERT INTO attempts (topic, score, difficulty, question_type, attempt_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (topic, 100.0 if item["correct"] else 0.0, difficulty, "mcq", attempt_id, ts),
            )

        for item in results.get("short_answer", []):
            conn.execute(
                """
                INSERT INTO attempts (topic, score, difficulty, question_type, attempt_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (topic, float(item["score"]), difficulty, "short_answer", attempt_id, ts),
            )

        conn.commit()


def get_topic_mastery(topic):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT score FROM attempts WHERE topic = ? ORDER BY id DESC LIMIT ?",
            (topic, ROLLING_WINDOW),
        ).fetchall()

    if not rows:
        return None

    scores = [float(row[0]) for row in rows]
    return round(sum(scores) / len(scores), 1)


def get_recommended_difficulty(topic):
    mastery = get_topic_mastery(topic)
    if mastery is None:
        return "medium"
    if mastery < 50:
        return "easy"
    if mastery < 80:
        return "medium"
    return "hard"


def get_all_topics_summary():
    with sqlite3.connect(DB_PATH) as conn:
        topics = [row[0] for row in conn.execute("SELECT DISTINCT topic FROM attempts").fetchall()]
        summary = []

        for topic in topics:
            count = conn.execute(
                "SELECT COUNT(DISTINCT COALESCE(attempt_id, timestamp)) FROM attempts WHERE topic = ?",
                (topic,),
            ).fetchone()[0]

            mastery = get_topic_mastery(topic)
            summary.append({"topic": topic, "mastery": mastery, "attempts": count})

        return summary


def get_topic_attempt_history(topic, limit=20):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(attempt_id, timestamp) as group_key, AVG(score), MIN(timestamp) as ts
            FROM attempts
            WHERE topic = ?
            GROUP BY group_key
            ORDER BY ts ASC
            """,
            (topic,),
        ).fetchall()

    history = [{"score": round(row[1], 1)} for row in rows]
    return history[-limit:] if limit else history


def get_weak_topics(threshold=WEAK_TOPIC_THRESHOLD):
    return [
        topic
        for topic in get_all_topics_summary()
        if topic["mastery"] is not None and topic["mastery"] < threshold
    ]


if __name__ == "__main__":
    init_db()
    print("Progress database initialized.")