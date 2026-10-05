import logging

log = logging.getLogger(__name__)


class SimulatedSerial:
    """Serial de desarrollo: solo registra. Se reemplaza por SerialService (Fase 5)."""

    def send_turn(self, turn_number: int) -> None:
        log.info("SIMULATED SERIAL TX turn=%s", turn_number)
