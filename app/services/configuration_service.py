from dataclasses import asdict, fields

from app.database.config_repository import ConfigRepository
from app.models.configuration import Configuration


class ConfigurationService:
    """Lee y guarda la configuración local en SQLite (tabla configuration)."""

    def __init__(self, repository: ConfigRepository):
        self._repo = repository

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

    def is_terminal_configured(self) -> bool:
        cfg = self.load()
        return bool(cfg.terminal_id and cfg.hub_url)
