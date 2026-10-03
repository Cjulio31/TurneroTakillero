from datetime import datetime

from app.database.database import Database


class ConfigRepository:
    def __init__(self, db: Database):
        self._conn = db.conn

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute(
            "SELECT config_value FROM configuration WHERE config_key = ?", (key,)
        ).fetchone()
        return row["config_value"] if row else default

    def set(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO configuration (config_key, config_value, updated_at)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT(config_key) DO UPDATE SET"
                " config_value = excluded.config_value, updated_at = excluded.updated_at",
                (key, str(value), datetime.now().isoformat(timespec="seconds")),
            )

    def all(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT config_key, config_value FROM configuration").fetchall()
        return {r["config_key"]: r["config_value"] for r in rows}
