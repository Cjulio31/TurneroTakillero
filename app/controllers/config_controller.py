from dataclasses import replace

from app.hardware.serial_device import list_serial_ports
from app.models.configuration import Configuration
from app.services.autostart import AutostartStore, NullAutostart
from app.services.configuration_service import ConfigurationService

THEME_VALUES = ("light", "dark")


class ConfigController:
    def __init__(self, service: ConfigurationService, autostart: AutostartStore | None = None):
        self._service = service
        self._autostart = autostart if autostart is not None else NullAutostart()

    def load(self) -> Configuration:
        return self._service.load()

    def update(self, **changes) -> Configuration:
        """Valida y guarda solo los campos indicados. Lanza ValueError si son inválidos."""
        cfg = replace(self._service.load(), **changes)
        self.validate(cfg)
        self._service.save(cfg)
        return cfg

    # --- inicio con Windows (vive en el registro del sistema, no en SQLite) -----------------
    def autostart_supported(self) -> bool:
        return self._autostart.is_supported()

    def autostart_enabled(self) -> bool:
        return self._autostart.is_enabled()

    def set_autostart(self, enabled: bool) -> None:
        """Activa o desactiva el inicio con el sistema. Lanza AutostartError si falla."""
        if enabled != self._autostart.is_enabled():
            self._autostart.set_enabled(enabled)

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
        for header in (cfg.serial_header_1, cfg.serial_header_2):
            if not 0 <= header <= 255:
                raise ValueError("Los bytes de cabecera del serial deben estar entre 0 y 255")
        if cfg.theme not in THEME_VALUES:
            raise ValueError("El tema debe ser 'light' o 'dark'")

    @staticmethod
    def available_serial_ports() -> list[str]:
        return list_serial_ports()
