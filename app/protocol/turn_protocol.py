from app.utils import constants
from app.utils.validators import is_valid_turn


def _is_byte(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 255


class TurnProtocol:
    """Protocolo serial: <byte 1> <byte 2> <turno (1 byte)>; por defecto 0x99 0x55 (153, 85).

    Los dos bytes de cabecera son configurables. Sin CRC, checksum, ACK ni bytes extra hasta
    confirmar con el dispositivo receptor.
    """

    def __init__(
        self,
        header_1: int = constants.SERIAL_HEADER_1,
        header_2: int = constants.SERIAL_HEADER_2,
    ):
        if not (_is_byte(header_1) and _is_byte(header_2)):
            raise ValueError(f"Cabecera fuera de rango (0-255): {header_1!r}, {header_2!r}")
        self.header_1 = header_1
        self.header_2 = header_2

    def build_packet(self, turn_number: int) -> bytes:
        if not is_valid_turn(turn_number):
            raise ValueError(
                f"Turno fuera de rango ({constants.MIN_TURN}-{constants.MAX_TURN}): {turn_number!r}"
            )
        return bytes([self.header_1, self.header_2, turn_number])

    @staticmethod
    def format_packet(packet: bytes) -> str:
        """Representación hexadecimal para logs: '99 55 19'."""
        return packet.hex(" ").upper()
