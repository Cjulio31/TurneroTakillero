from collections import deque
from dataclasses import dataclass

from app.controllers.app_state import AppState
from app.database.database import Database
from app.protocol.turn_protocol import TurnProtocol
from app.services.errors import PrintError, SerialSendError, SerialUnavailableError
from app.services.printer_service import PrinterService
from app.services.serial_service import SerialService
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

    def __init__(
        self,
        state: AppState,
        db: Database,
        serial: SerialService | None = None,
        printer: PrinterService | None = None,
    ):
        self.state = state
        self._db = db
        self._serial = serial
        self._printer = printer

    def check_database(self) -> DiagnosticResult:
        ok = self._db.is_ok()
        return DiagnosticResult(ok, "Base de datos OK" if ok else "Falla en la base de datos")

    def test_hub(self) -> DiagnosticResult:
        return _pending(3)

    def test_serial(self) -> DiagnosticResult:
        if self._serial is None:
            return DiagnosticResult(False, "El servicio serial no está activo")
        status = self._serial.get_status()
        if status.connected:
            return DiagnosticResult(True, f"Serial conectado en {status.port}")
        self._serial.reconnect()  # asíncrono: el indicador se actualiza al terminar
        reason = status.error or "sin detalle"
        return DiagnosticResult(False, f"Serial desconectado ({reason}). Reintentando conexión…")

    def test_printer(self) -> DiagnosticResult:
        if self._printer is None:
            return DiagnosticResult(False, "El servicio de impresión no está activo")
        if not self._printer.refresh_status():
            return DiagnosticResult(False, "Impresora no disponible")
        try:
            self._printer.test()  # ticket de prueba: no crea turnos ni toca la secuencia
        except PrintError as exc:
            return DiagnosticResult(False, f"Falló la impresión de prueba: {exc}")
        return DiagnosticResult(True, "Ticket de prueba enviado a la impresora")

    def send_test_turn(self, turn_number: int) -> DiagnosticResult:
        if not is_valid_turn(turn_number):
            return DiagnosticResult(
                False, f"Turno inválido: use {constants.MIN_TURN}-{constants.MAX_TURN}"
            )
        if self._serial is None:
            return DiagnosticResult(False, "El servicio serial no está activo")
        # Va directo al serial: no crea turnos ni toca la secuencia de producción.
        try:
            self._serial.send_turn(turn_number)
        except (SerialUnavailableError, SerialSendError) as exc:
            return DiagnosticResult(False, f"No se pudo enviar el turno de prueba: {exc}")
        protocol = TurnProtocol()
        packet = protocol.format_packet(protocol.build_packet(turn_number))
        return DiagnosticResult(True, f"TX: {packet} (x{self._serial.transmissions})")

    @staticmethod
    def read_log_tail(lines: int = 200) -> str:
        path = constants.LOG_PATH
        if not path.exists():
            return ""
        with path.open(encoding="utf-8", errors="replace") as fh:
            return "".join(deque(fh, maxlen=lines))
