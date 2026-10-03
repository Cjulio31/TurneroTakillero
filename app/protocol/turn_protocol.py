from app.utils import constants
from app.utils.validators import is_valid_turn


class TurnProtocol:
    """Protocolo serial existente: 0x99 0x55 <turno (1 byte)>.

    Sin CRC, checksum, ACK ni bytes extra hasta confirmar con el dispositivo receptor.
    """

    def build_packet(self, turn_number: int) -> bytes:
        if not is_valid_turn(turn_number):
            raise ValueError(
                f"Turno fuera de rango ({constants.MIN_TURN}-{constants.MAX_TURN}): {turn_number!r}"
            )
        return bytes([constants.SERIAL_HEADER_1, constants.SERIAL_HEADER_2, turn_number])

    @staticmethod
    def format_packet(packet: bytes) -> str:
        """Representación hexadecimal para logs: '99 55 19'."""
        return packet.hex(" ").upper()
