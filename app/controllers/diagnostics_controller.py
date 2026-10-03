from collections import deque
from dataclasses import dataclass

from app.controllers.app_state import AppState
from app.database.database import Database
from app.utils import constants
from app.utils.validators import is_valid_turn


@dataclass
class DiagnosticResult:
    ok: bool
    message: str


def _pending(phase: int) -> DiagnosticResult:
    return DiagnosticResult(False, f"No disponible aún: se implementa en la Fase {phase}.")


class DiagnosticsController:
    """Las pruebas reales se conectan a los servicios en las fases 3 a 7."""

    def __init__(self, state: AppState, db: Database):
        self.state = state
        self._db = db

    def check_database(self) -> DiagnosticResult:
        ok = self._db.is_ok()
        return DiagnosticResult(ok, "Base de datos OK" if ok else "Falla en la base de datos")

    def test_hub(self) -> DiagnosticResult:
        return _pending(3)

    def test_serial(self) -> DiagnosticResult:
        return _pending(5)

    def test_printer(self) -> DiagnosticResult:
        return _pending(6)

    def send_test_turn(self, turn_number: int) -> DiagnosticResult:
        if not is_valid_turn(turn_number):
            return DiagnosticResult(
                False, f"Turno inválido: use {constants.MIN_TURN}-{constants.MAX_TURN}"
            )
        return _pending(5)

    @staticmethod
    def read_log_tail(lines: int = 200) -> str:
        path = constants.LOG_PATH
        if not path.exists():
            return ""
        with path.open(encoding="utf-8", errors="replace") as fh:
            return "".join(deque(fh, maxlen=lines))
