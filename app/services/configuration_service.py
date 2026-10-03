import logging
from collections.abc import Callable
from dataclasses import asdict, fields

from app.database.config_repository import ConfigRepository
from app.models.configuration import Configuration

log = logging.getLogger(__name__)


class ConfigurationService:
    """Lee y guarda la configuración local en SQLite (tabla configuration)."""

    def __init__(self, repository: ConfigRepository):
        self._repo = repository
        self._listeners: list[Callable[[Configuration], None]] = []

    def add_listener(self, listener: Callable[[Configuration], None]) -> None:
        """Avisa a los servicios cuando se guarda la configuración."""
        self._listeners.append(listener)

    def load(self) -> Configuration:
        stored = self._repo.all()
        defaults = Configuration()
        values = {}
        for f in fields(Configuration):
            raw = stored.get(f.name)
            default = getattr(defaults, f.name)
            if raw is None:
                values[f.name] = default
            elif isinstance(default, int):
                try:
                    values[f.name] = int(raw)
                except ValueError:
                    values[f.name] = default
            else:
                values[f.name] = raw
        return Configuration(**values)

    def save(self, config: Configuration) -> None:
        for key, value in asdict(config).items():
            self._repo.set(key, str(value))
        for listener in self._listeners:
            try:
                listener(config)
            except Exception:  # un listener defectuoso no debe impedir guardar
                log.exception("Error en listener de configuración")

    def is_terminal_configured(self) -> bool:
        cfg = self.load()
        return bool(cfg.terminal_id and cfg.hub_url)
