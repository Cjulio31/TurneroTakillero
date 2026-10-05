import logging
import sqlite3
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer, Signal

from app.controllers import app_state as st
from app.controllers.app_state import COMPONENTS, AppState
from app.database.database import Database
from app.database.turn_repository import TurnRepository
from app.utils import constants

log = logging.getLogger(__name__)

HEALTH_INTERVAL_MS = 10_000

LEVEL_OK = "OK"
LEVEL_DEGRADED = "DEGRADED"  # la app funciona, pero hay algo que atender
LEVEL_DOWN = "DOWN"  # no se puede garantizar la persistencia de turnos

_GOOD = (st.CONNECTED, st.READY, st.AVAILABLE, st.OK)
_STATE_TEXT = {
    st.CONNECTING: "conectando",
    st.DISCONNECTED: "desconectado",
    st.UNAVAILABLE: "no disponible",
    st.ERROR: "con error",
    st.UNKNOWN: "sin datos",
}
_LABELS = {"hub": "HUB", "serial": "Serial", "printer": "Impresora", "database": "Base de datos"}


@dataclass(frozen=True)
class HealthReport:
    level: str
    components: dict[str, str] = field(default_factory=dict)
    pending: int = 0  # turnos sin COMPLETED
    errors: int = 0  # turnos en ERROR (requieren atención manual)
    problems: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        if self.level == LEVEL_OK:
            return "Todo en orden"
        return "; ".join(self.problems)


class HealthService(QObject):
    """Monitorea el estado global: componentes (hub, serial, impresora, base de datos) y turnos.

    No toca hardware ni turnos: lee `AppState` y SQLite. La base de datos es el único componente
    que mide él mismo (`ping` periódico, `integrity_check` al arrancar); los demás los actualizan
    sus servicios. Emite `report_changed` solo cuando el informe cambia.
    """

    report_changed = Signal(object)  # HealthReport

    def __init__(
        self,
        state: AppState,
        db: Database,
        turns: TurnRepository,
        interval_ms: int = HEALTH_INTERVAL_MS,
    ):
        super().__init__()
        self._state = state
        self._db = db
        self._turns = turns
        self._last: HealthReport | None = None
        self._integrity_ok = True
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.check)
        state.status_changed.connect(self._on_status_changed)

    def start(self) -> HealthReport:
        """Chequeo completo al arrancar (incluye integrity_check) y luego periódico."""
        self._integrity_ok = self._db.is_ok()
        if not self._integrity_ok:  # persistente hasta reiniciar: no se enmascara con un ping
            log.error("La verificación de integridad de la base de datos falló")
        self._timer.start()
        return self.check()

    def stop(self) -> None:
        self._timer.stop()

    def check(self) -> HealthReport:
        """Mide la base de datos, recalcula el informe y lo emite si cambió."""
        alive = self._db.ping() and self._integrity_ok
        previous = self._state.status("database")
        if alive and previous == st.ERROR:
            log.info("La base de datos volvió a responder")
        elif not alive and previous != st.ERROR:
            log.error("La base de datos no responde")
        self._state.set_status("database", st.OK if alive else st.ERROR)
        return self._publish()

    def report(self) -> HealthReport:
        """Informe actual sin medir ni emitir (para la UI)."""
        return self._build()

    def _on_status_changed(self, component: str, _status: str) -> None:
        if component in COMPONENTS:
            self._publish()

    def _publish(self) -> HealthReport:
        report = self._build()
        if report != self._last:
            self._last = report
            self.report_changed.emit(report)
        return report

    def _build(self) -> HealthReport:
        components = {c: self._state.status(c) for c in COMPONENTS}
        problems = [
            f"{_LABELS[c]} {_STATE_TEXT.get(s, s.lower())}"
            for c, s in components.items()
            if s not in _GOOD
        ]
        try:
            counts = self._turns.count_by_status()
        except sqlite3.Error:
            log.exception("No se pudo leer el conteo de turnos")
            counts = {}
            components["database"] = st.ERROR
            problems.append("Base de datos con error")
        errors = counts.get(constants.STATUS_ERROR, 0)
        pending = sum(n for s, n in counts.items() if s in constants.PENDING_STATUSES)
        if errors:
            problems.append(f"{errors} turno(s) en error")
        if components["database"] == st.ERROR:
            level = LEVEL_DOWN
        elif problems:
            level = LEVEL_DEGRADED
        else:
            level = LEVEL_OK
        return HealthReport(level, components, pending, errors, tuple(problems))
