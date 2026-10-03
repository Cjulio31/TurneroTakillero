from datetime import datetime

from app.database.database import Database


class EventRepository:
    def __init__(self, db: Database):
        self._conn = db.conn

    def add(self, event_type: str, message: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO events (event_type, message, created_at) VALUES (?, ?, ?)",
                (event_type, message, datetime.now().isoformat(timespec="seconds")),
            )

    def recent(self, limit: int = 100) -> list[dict]:
        rows = self._conn.execute(
            "SELECT event_type, message, created_at FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
