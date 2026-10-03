from typing import Protocol

from app.models.turn import Turn


class TurnSerialPort(Protocol):
    """Lo que TurnService necesita del serial. Lo implementará SerialService (Fase 5)."""

    def send_turn(self, turn_number: int) -> None:
        """Envía el turno al dispositivo.

        Lanza SerialUnavailableError si no hay puerto (nada enviado) o SerialSendError si falló
        durante el envío (resultado incierto).
        """


class TicketPrinter(Protocol):
    """Lo que TurnService necesita de la impresora. Lo implementará PrinterService (Fase 6)."""

    def print_ticket(self, turn: Turn) -> None:
        """Imprime el ticket. Lanza PrintError si falla."""
