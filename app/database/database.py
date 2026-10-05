import sqlite3
from pathlib import Path

from app.utils import constants

SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL UNIQUE,
    terminal_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    received_at DATETIME NOT NULL,
    processed_at DATETIME NULL,
    sent_at DATETIME NULL,
    printed_at DATETIME NULL,
    completed_at DATETIME NULL,
    error_code TEXT NULL,
    error_message TEXT NULL,
    ack_status TEXT NULL,
    acked_at DATETIME NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_status ON turns(status);

CREATE TABLE IF NOT EXISTS configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME NOT NULL
);
"""


class Database:
    """Conexión SQLite. Cada hilo debe usar su propia instancia (check_same_thread)."""

    def __init__(self, path: Path | str | None = None):
        self.path = str(path or constants.DATABASE_PATH)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Agrega columnas nuevas a bases creadas por versiones anteriores."""
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(turns)")}
        for name, ddl in (("ack_status", "TEXT NULL"), ("acked_at", "DATETIME NULL")):
            if name not in columns:
                self.conn.execute(f"ALTER TABLE turns ADD COLUMN {name} {ddl}")

    def is_ok(self) -> bool:
        try:
            return self.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        except sqlite3.Error:
            return False

    def ping(self) -> bool:
        """Chequeo barato para el monitoreo periódico (integrity_check es costoso)."""
        try:
            self.conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def close(self) -> None:
        self.conn.close()
