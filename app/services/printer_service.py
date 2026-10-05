import logging
import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer

from app.controllers import app_state as st
from app.controllers.app_state import AppState
from app.database.event_repository import EventRepository
from app.hardware.printer_backend import PrinterBackend, create_backend
from app.hardware.ticket import build_test_ticket, build_ticket
from app.models.configuration import Configuration
from app.models.turn import Turn
from app.services.errors import PrintError
from app.utils import constants

log = logging.getLogger(__name__)

HEALTH_INTERVAL_MS = 5000

BackendFactory = Callable[[str, str], PrinterBackend]


class PrinterService(QObject):
    """Impresión de tickets: `print_ticket` (turnos), `test` (prueba) e `is_available`.

    Cualquier fallo se convierte en PrintError; TurnService pasa el turno a ERROR conservando
    su message_id y el reintento manual no reenvía el serial. Imprime de forma síncrona en el
    hilo que lo invoque (el spooler del SO encola el trabajo).
    """

    def __init__(
        self,
        state: AppState,
        events: EventRepository,
        config_provider: Callable[[], Configuration],
        backend_factory: BackendFactory = create_backend,
        health_interval_ms: int = HEALTH_INTERVAL_MS,
    ):
        super().__init__()
        self._state = state
        self._events = events
        self._config = config_provider
        self._factory = backend_factory
        self._lock = threading.Lock()
        self._backend: PrinterBackend | None = None
        self._key: tuple[str, str] | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(health_interval_ms)
        self._timer.timeout.connect(self.refresh_status)

    def start(self) -> None:
        self.refresh_status()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._state.set_status("printer", st.UNAVAILABLE)

    def on_config_changed(self) -> None:
        self.refresh_status()

    def _current(self) -> PrinterBackend:
        cfg = self._config()
        key = (cfg.printer_type, cfg.printer_port)
        with self._lock:
            if self._backend is None or key != self._key:
                self._backend = self._factory(*key)
                self._key = key
            return self._backend

    def is_available(self) -> bool:
        try:
            return self._current().is_available()
        except Exception:  # un backend defectuoso no debe tumbar la app
            log.exception("Error al consultar la impresora")
            return False

    def refresh_status(self) -> bool:
        available = self.is_available()
        self._state.set_status("printer", st.AVAILABLE if available else st.UNAVAILABLE)
        return available

    def print_ticket(self, turn: Turn) -> None:
        cfg = self._config()
        ticket = build_ticket(turn, cfg.terminal_name, cfg.terminal_location)
        self._print(ticket, f"turno {turn.turn_number} ({turn.message_id})")

    def test(self) -> None:
        """Ticket de prueba: no crea turnos ni afecta la secuencia."""
        cfg = self._config()
        self._print(build_test_ticket(cfg.terminal_name, cfg.terminal_location), "prueba")

    def _print(self, ticket, what: str) -> None:
        try:
            self._current().print_ticket(ticket)
        except PrintError as exc:
            self._failed(what, str(exc))
            raise
        except Exception as exc:
            log.exception("Fallo inesperado al imprimir %s", what)
            self._failed(what, str(exc))
            raise PrintError(str(exc)) from exc
        self._state.set_status("printer", st.AVAILABLE)
        log.info("PRINT OK: %s", what)

    def _failed(self, what: str, reason: str) -> None:
        log.error("PRINT failed (%s): %s", what, reason)
        if what == "prueba":  # los turnos los registra TurnService
            self._events.add(constants.EVENT_PRINT_ERROR, f"{what}: {reason}")
        self.refresh_status()
