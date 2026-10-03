from dataclasses import replace

from app.hardware.serial_device import list_serial_ports
from app.models.configuration import Configuration
from app.services.configuration_service import ConfigurationService


class ConfigController:
    def __init__(self, service: ConfigurationService):
        self._service = service

    def load(self) -> Configuration:
        return self._service.load()

    def update(self, **changes) -> Configuration:
        """Valida y guarda solo los campos indicados. Lanza ValueError si son inválidos."""
        cfg = replace(self._service.load(), **changes)
        self.validate(cfg)
        self._service.save(cfg)
        return cfg

    @staticmethod
    def validate(cfg: Configuration) -> None:
        if cfg.hub_url and not cfg.hub_url.lower().startswith(
            ("http://", "https://", "ws://", "wss://")
        ):
            raise ValueError("La URL del HUB debe iniciar con http(s):// o ws(s)://")
        if cfg.hub_url and not cfg.terminal_id.strip():
            raise ValueError("Debe indicar el Terminal ID")
        if cfg.hub_timeout < 1:
            raise ValueError("El timeout debe ser mayor a 0")
        if cfg.reconnect_interval < 1:
            raise ValueError("El intervalo de reconexión debe ser mayor a 0")
        if cfg.serial_transmissions < 1:
            raise ValueError("Las transmisiones deben ser al menos 1")

    @staticmethod
    def available_serial_ports() -> list[str]:
        return list_serial_ports()
