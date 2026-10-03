import logging

from app.models.turn import Turn

log = logging.getLogger(__name__)


class SimulatedSerial:
    """Serial de desarrollo: solo registra. Se reemplaza por SerialService (Fase 5)."""

    def send_turn(self, turn_number: int) -> None:
        log.info("SIMULATED SERIAL TX turn=%s", turn_number)


class SimulatedPrinter:
    """Impresora de desarrollo: solo registra. Se reemplaza por PrinterService (Fase 6)."""

    def print_ticket(self, turn: Turn) -> None:
        log.info("SIMULATED PRINT turn=%s message_id=%s", turn.turn_number, turn.message_id)
