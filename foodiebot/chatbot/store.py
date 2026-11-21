"""SQLite conversation log used for analytics and user feedback."""
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    user_text   TEXT NOT NULL,
    bot_text    TEXT NOT NULL,
    intent      TEXT NOT NULL,
    confidence  REAL NOT NULL,
    latency_ms  REAL NOT NULL,
    feedback    INTEGER          -- 1 = helpful, -1 = not helpful, NULL = none
);
"""


class ChatStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def log(self, session_id: str, user_text: str, reply: dict) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO messages (created_at, session_id, user_text, bot_text, intent, confidence, latency_ms)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), session_id, user_text,
                 reply["reply"], reply["intent"], reply["confidence"], reply["latency_ms"]),
            )
            return cur.lastrowid

    def set_feedback(self, message_id: int, helpful: bool) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE messages SET feedback = ? WHERE id = ?", (1 if helpful else -1, message_id)
            )
            return cur.rowcount == 1

    def stats(self) -> dict:
        with self._lock:
            q = self._conn.execute
            total = q("SELECT COUNT(*) FROM messages").fetchone()[0]
            sessions = q("SELECT COUNT(DISTINCT session_id) FROM messages").fetchone()[0]
            fallback = q("SELECT COUNT(*) FROM messages WHERE intent = 'fallback'").fetchone()[0]
            avg = q("SELECT AVG(confidence), AVG(latency_ms) FROM messages WHERE intent != 'fallback'").fetchone()
            up = q("SELECT COUNT(*) FROM messages WHERE feedback = 1").fetchone()[0]
            down = q("SELECT COUNT(*) FROM messages WHERE feedback = -1").fetchone()[0]
            top = q("SELECT intent, COUNT(*) AS n FROM messages GROUP BY intent ORDER BY n DESC LIMIT 10").fetchall()
            unanswered = q(
                "SELECT user_text, confidence, created_at FROM messages WHERE intent = 'fallback'"
                " ORDER BY id DESC LIMIT 10"
            ).fetchall()
            recent = q(
                "SELECT user_text, intent, confidence, feedback, created_at FROM messages ORDER BY id DESC LIMIT 15"
            ).fetchall()
        return {
            "total_messages": total,
            "sessions": sessions,
            "answer_rate": round(1 - fallback / total, 3) if total else None,
            "avg_confidence": round(avg[0], 3) if avg[0] is not None else None,
            "avg_latency_ms": round(avg[1], 2) if avg[1] is not None else None,
            "feedback": {"helpful": up, "not_helpful": down,
                         "satisfaction": round(up / (up + down), 3) if (up + down) else None},
            "top_intents": [dict(r) for r in top],
            "unanswered": [dict(r) for r in unanswered],
            "recent": [dict(r) for r in recent],
        }
