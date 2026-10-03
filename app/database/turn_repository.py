import sqlite3
from datetime import datetime

from app.database.database import Database
from app.models.turn import Turn
from app.utils import constants

_STATUS_TIMESTAMP = {
    constants.STATUS_PROCESSING: "processed_at",
    constants.STATUS_SENT: "sent_at",
    constants.STATUS_PRINTED: "printed_at",
    constants.STATUS_COMPLETED: "completed_at",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _to_turn(row: sqlite3.Row) -> Turn:
    return Turn(**dict(row))


class TurnRepository:
    def __init__(self, db: Database):
        self._conn = db.conn

    def add(self, message_id: str, terminal_id: str, turn_number: int) -> Turn | None:
        """Inserta un turno RECEIVED. Devuelve None si el message_id ya existe (duplicado)."""
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO turns (message_id, terminal_id, turn_number, status, received_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (message_id, terminal_id, turn_number, constants.STATUS_RECEIVED, _now()),
                )
        except sqlite3.IntegrityError:
            return None
        return self.get_by_message_id(message_id)

    def get_by_message_id(self, message_id: str) -> Turn | None:
        row = self._conn.execute(
            "SELECT * FROM turns WHERE message_id = ?", (message_id,)
        ).fetchone()
        return _to_turn(row) if row else None

    def exists(self, message_id: str) -> bool:
        return self.get_by_message_id(message_id) is not None

    def update_status(
        self,
        message_id: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if status not in constants.TURN_STATUSES:
            raise ValueError(f"Estado inválido: {status}")
        column = _STATUS_TIMESTAMP.get(status)
        sets = ["status = ?", "error_code = ?", "error_message = ?"]
        params: list[object] = [status, error_code, error_message]
        if column:
            sets.append(f"{column} = ?")
            params.append(_now())
        params.append(message_id)
        with self._conn:
            cur = self._conn.execute(
                f"UPDATE turns SET {', '.join(sets)} WHERE message_id = ?", params
            )
        if cur.rowcount == 0:
            raise KeyError(message_id)

    def list_pending(self) -> list[Turn]:
        marks = ",".join("?" * len(constants.PENDING_STATUSES))
        rows = self._conn.execute(
            f"SELECT * FROM turns WHERE status IN ({marks}) ORDER BY id",
            constants.PENDING_STATUSES,
        ).fetchall()
        return [_to_turn(r) for r in rows]

    def list_by_status(self, statuses: tuple[str, ...]) -> list[Turn]:
        marks = ",".join("?" * len(statuses))
        rows = self._conn.execute(
            f"SELECT * FROM turns WHERE status IN ({marks}) ORDER BY id", statuses
        ).fetchall()
        return [_to_turn(r) for r in rows]

    def mark_acked(self, message_id: str, status: str) -> None:
        """Registra que el HUB ya fue informado de este estado del turno."""
        with self._conn:
            self._conn.execute(
                "UPDATE turns SET ack_status = ?, acked_at = ? WHERE message_id = ?",
                (status, _now(), message_id),
            )

    def list_unacked(self) -> list[Turn]:
        """Turnos en estado final (COMPLETED/ERROR) cuyo estado el HUB aún no confirmó."""
        rows = self._conn.execute(
            "SELECT * FROM turns WHERE status IN (?, ?)"
            " AND (ack_status IS NULL OR ack_status != status) ORDER BY id",
            (constants.STATUS_COMPLETED, constants.STATUS_ERROR),
        ).fetchall()
        return [_to_turn(r) for r in rows]

    def last(self) -> Turn | None:
        row = self._conn.execute("SELECT * FROM turns ORDER BY id DESC LIMIT 1").fetchone()
        return _to_turn(row) if row else None

    def search(
        self,
        date: str | None = None,
        turn_number: int | None = None,
        status: str | None = None,
        limit: int = 500,
    ) -> list[Turn]:
        where, params = [], []
        if date:
            where.append("substr(received_at, 1, 10) = ?")
            params.append(date)
        if turn_number is not None:
            where.append("turn_number = ?")
            params.append(turn_number)
        if status:
            where.append("status = ?")
            params.append(status)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self._conn.execute(
            f"SELECT * FROM turns {clause} ORDER BY id DESC LIMIT ?", [*params, limit]
        ).fetchall()
        return [_to_turn(r) for r in rows]
