from dataclasses import dataclass

import serial
from serial.tools import list_ports

from app.models.configuration import Configuration


@dataclass(frozen=True)
class SerialSettings:
    port: str = ""
    baudrate: int = 9600
    data_bits: int = 8
    parity: str = "N"
    stop_bits: int = 1
    transmissions: int = 2

    @classmethod
    def from_config(cls, cfg: Configuration) -> "SerialSettings":
        return cls(
            port=cfg.serial_port,
            baudrate=cfg.baudrate,
            data_bits=cfg.data_bits,
            parity=cfg.parity,
            stop_bits=cfg.stop_bits,
            transmissions=cfg.serial_transmissions,
        )

    @property
    def connection_key(self) -> tuple:
        """Parámetros que obligan a reabrir el puerto (las transmisiones no)."""
        return (self.port, self.baudrate, self.data_bits, self.parity, self.stop_bits)


def list_serial_ports() -> list[str]:
    return sorted(p.device for p in list_ports.comports())


class SerialDevice:
    """Envoltorio mínimo de pyserial. `port` puede ser una URL de pyserial (p. ej. loop://)."""

    def __init__(self, port: serial.SerialBase):
        self._port = port

    @classmethod
    def open(cls, settings: SerialSettings, timeout: float = 1.0) -> "SerialDevice":
        port = serial.serial_for_url(
            settings.port,
            baudrate=settings.baudrate,
            bytesize=settings.data_bits,
            parity=settings.parity,
            stopbits=settings.stop_bits,
            timeout=timeout,
            write_timeout=timeout,
        )
        return cls(port)

    @property
    def is_open(self) -> bool:
        return bool(self._port.is_open)

    def write(self, data: bytes) -> int:
        # Sin flush(): en Windows (FlushFileBuffers) ignora write_timeout y puede bloquear el
        # hilo principal para siempre si el dispositivo no drena. write() ya respeta write_timeout.
        return self._port.write(data)

    def read(self, size: int = 1) -> bytes:
        return self._port.read(size)

    def close(self) -> None:
        self._port.close()
