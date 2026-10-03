import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.controllers import app_state as st
from app.controllers.app_state import AppState
from app.database.event_repository import EventRepository
from app.database.turn_repository import TurnRepository
from app.models.turn import Turn
from app.protocol.message_validator import MessageRejected, parse_message
from app.services.errors import PrintError, SerialUnavailableError
from app.services.ports import TicketPrinter, TurnSerialPort
from app.utils import constants

log = logging.getLogger(__name__)

OUTCOME_REJECTED = "REJECTED"
OUTCOME_DUPLICATE = "DUPLICATE"
OUTCOME_COMPLETED = "COMPLETED"
OUTCOME_PENDING = "PENDING"  # guardado, esperando que el serial esté disponible
OUTCOME_ERROR = "ERROR"

ERR_SERIAL_UNAVAILABLE = "SERIAL_UNAVAILABLE"
ERR_SERIAL = "SERIAL_ERROR"
ERR_PRINT = "PRINT_ERROR"
ERR_INTERRUPTED = "INTERRUPTED"


@dataclass
class HandleResult:
    outcome: str
    message_id: str | None = None
    detail: str = ""


class TurnService(QObject):
    """Recibe turnos crudos, los valida, persiste, envía al serial, imprime y confirma al HUB.

    Reglas: persistir antes de procesar; un message_id se procesa una sola vez (idempotencia);
    un turno COMPLETED jamás se reprocesa; sin reintento serial a ciegas.
    Corre de forma síncrona en el hilo que lo invoque (en las fases 5-6 los dispositivos
    se pasarán por workers sin cambiar esta lógica).
    """

    turn_changed = Signal(str)  # message_id

    def __init__(
        self,
        turns: TurnRepository,
        events: EventRepository,
        state: AppState,
        serial: TurnSerialPort,
        printer: TicketPrinter,
        ack_sender: Callable[[str, str], bool],
        terminal_id: Callable[[], str],
    ):
        super().__init__()
        self._turns = turns
        self._events = events
        self._state = state
        self._serial = serial
        self._printer = printer
        self._send_ack = ack_sender
        self._terminal_id = terminal_id
        self._busy = False
        state.status_changed.connect(self._on_status_changed)

    # --- entrada ---------------------------------------------------------------------------
    def handle_message(self, payload: Any) -> HandleResult:
        try:
            msg = parse_message(payload, self._terminal_id())
        except MessageRejected as exc:
            log.warning("Mensaje rechazado: %s", exc)
            self._events.add(constants.EVENT_TURN_REJECTED, str(exc))
            if exc.message_id:
                self._ack(exc.message_id, "REJECTED", persist=False)
            return HandleResult(OUTCOME_REJECTED, exc.message_id, exc.code)

        existing = self._turns.get_by_message_id(msg.message_id)
        if existing is not None:
            return self._handle_duplicate(existing)

        turn = self._turns.add(msg.message_id, msg.terminal_id, msg.turn)
        if turn is None:  # carrera: otro camino lo insertó entre la consulta y el alta
            return self._handle_duplicate(self._turns.get_by_message_id(msg.message_id))
        log.info("TURN RECEIVED: %03d (%s)", msg.turn, msg.message_id)
        self._events.add(constants.EVENT_TURN_RECEIVED, f"Turno {msg.turn:03d} {msg.message_id}")
        self._state.set_last_times(received=_clock())
        self.turn_changed.emit(msg.message_id)
        return self._process(msg.message_id)

    def _handle_duplicate(self, existing: Turn) -> HandleResult:
        log.info("Duplicado ignorado: %s (estado %s)", existing.message_id, existing.status)
        self._events.add(
            constants.EVENT_TURN_DUPLICATE, f"{existing.message_id} ya está {existing.status}"
        )
        if existing.status in (constants.STATUS_COMPLETED, constants.STATUS_ERROR):
            self._ack(existing.message_id, existing.status)  # confirma el estado anterior
        return HandleResult(OUTCOME_DUPLICATE, existing.message_id, existing.status)

    # --- procesamiento ---------------------------------------------------------------------
    def _process(self, message_id: str) -> HandleResult:
        turn = self._turns.get_by_message_id(message_id)
        self._turns.update_status(message_id, constants.STATUS_PROCESSING)
        self.turn_changed.emit(message_id)

        if turn.sent_at is None:  # un reintento tras error de impresión no reenvía el serial
            try:
                self._serial.send_turn(turn.turn_number)
            except SerialUnavailableError as exc:
                log.warning("Serial no disponible, turno %s queda pendiente: %s", message_id, exc)
                self._turns.update_status(
                    message_id, constants.STATUS_RECEIVED, ERR_SERIAL_UNAVAILABLE, str(exc)
                )
                self._events.add(constants.EVENT_SERIAL_ERROR, f"{message_id}: {exc}")
                self.turn_changed.emit(message_id)
                return HandleResult(OUTCOME_PENDING, message_id, ERR_SERIAL_UNAVAILABLE)
            except Exception as exc:  # resultado incierto: no se reintenta a ciegas
                log.exception("Fallo de envío serial para %s", message_id)
                self._events.add(constants.EVENT_SERIAL_ERROR, f"{message_id}: {exc}")
                return self._fail(message_id, ERR_SERIAL, str(exc))
            self._turns.update_status(message_id, constants.STATUS_SENT)
            self.turn_changed.emit(message_id)

        try:
            self._printer.print_ticket(self._turns.get_by_message_id(message_id))
        except Exception as exc:
            if not isinstance(exc, PrintError):
                log.exception("Fallo inesperado al imprimir %s", message_id)
            self._events.add(constants.EVENT_PRINT_ERROR, f"{message_id}: {exc}")
            return self._fail(message_id, ERR_PRINT, str(exc))

        self._turns.update_status(message_id, constants.STATUS_PRINTED)
        self._state.set_last_times(printed=_clock())
        return self._complete(message_id)

    def _complete(self, message_id: str) -> HandleResult:
        self._turns.update_status(message_id, constants.STATUS_COMPLETED)
        log.info("TURN COMPLETED: %s", message_id)
        self._events.add(constants.EVENT_TURN_COMPLETED, message_id)
        self.turn_changed.emit(message_id)
        self._ack(message_id, constants.STATUS_COMPLETED)
        return HandleResult(OUTCOME_COMPLETED, message_id)

    def _fail(self, message_id: str, code: str, message: str) -> HandleResult:
        self._turns.update_status(message_id, constants.STATUS_ERROR, code, message)
        self.turn_changed.emit(message_id)
        self._ack(message_id, constants.STATUS_ERROR)
        return HandleResult(OUTCOME_ERROR, message_id, code)

    def _ack(self, message_id: str, status: str, persist: bool = True) -> bool:
        if not self._send_ack(message_id, status):
            return False
        if persist:
            self._turns.mark_acked(message_id, status)
        return True

    # --- reintentos, recuperación y sincronización -----------------------------------------
    def retry(self, message_id: str) -> HandleResult | None:
        """Reintento manual (mismo message_id). Solo para turnos en ERROR; nunca COMPLETED."""
        turn = self._turns.get_by_message_id(message_id)
        if turn is None or turn.status != constants.STATUS_ERROR:
            log.warning("Reintento ignorado para %s (estado %s)", message_id, turn and turn.status)
            return None
        log.info("Reintentando %s", message_id)
        return self._process(message_id)

    def process_pending(self) -> int:
        """Procesa los RECEIVED en orden de llegada. Se detiene si el serial sigue sin estar."""
        if self._busy:
            return 0
        self._busy = True
        done = 0
        try:
            for turn in self._turns.list_by_status((constants.STATUS_RECEIVED,)):
                if self._process(turn.message_id).outcome == OUTCOME_PENDING:
                    break
                done += 1
        finally:
            self._busy = False
        return done

    def recover_on_startup(self) -> dict[str, int]:
        """Política de recuperación tras un cierre inesperado.

        - RECEIVED: nunca se envió nada; se procesará con process_pending().
        - PROCESSING / SENT: no se sabe si el serial o la impresora llegaron a actuar -> ERROR
          para verificación manual y reintento explícito.
        - PRINTED: solo faltaba cerrar -> COMPLETED (y confirmar al HUB).
        - ERROR: se deja para reintento manual.
        """
        counts = {"to_error": 0, "completed": 0}
        for turn in self._turns.list_by_status(
            (constants.STATUS_PROCESSING, constants.STATUS_SENT)
        ):
            self._turns.update_status(
                turn.message_id,
                constants.STATUS_ERROR,
                ERR_INTERRUPTED,
                f"Interrumpido en {turn.status}: verificar si se envió/imprimió",
            )
            self._events.add(
                constants.EVENT_TURN_RECOVERED, f"{turn.message_id}: {turn.status} -> ERROR"
            )
            counts["to_error"] += 1
        for turn in self._turns.list_by_status((constants.STATUS_PRINTED,)):
            self._turns.update_status(turn.message_id, constants.STATUS_COMPLETED)
            self._events.add(
                constants.EVENT_TURN_RECOVERED, f"{turn.message_id}: PRINTED -> COMPLETED"
            )
            counts["completed"] += 1
        log.info("Recuperación al iniciar: %s", counts)
        return counts

    def startup(self) -> dict[str, int]:
        counts = self.recover_on_startup()
        self.process_pending()
        return counts

    def sync_pending_acks(self) -> int:
        """Informa al HUB los estados finales aún no confirmados. No reprocesa ningún turno."""
        sent = 0
        for turn in self._turns.list_unacked():
            if not self._ack(turn.message_id, turn.status):
                break  # sin canal: se reintentará al volver la conexión
            sent += 1
        return sent

    def _on_status_changed(self, component: str, status: str) -> None:
        if component == "hub" and status == st.READY:
            self.sync_pending_acks()
        elif component == "serial" and status in (st.CONNECTED, st.READY, st.AVAILABLE):
            self.process_pending()


def _clock() -> str:
    return datetime.now().strftime("%H:%M:%S")
