import logging
from collections.abc import Callable
from dataclasses import asdict, fields

from app.database.config_repository import ConfigRepository
from app.models.configuration import Configuration
from app.services.errors import SecretStoreError
from app.services.secret_store import InMemorySecretStore, SecretStore

log = logging.getLogger(__name__)

TOKEN_SECRET = "api_token"


class ConfigurationService:
    """Lee y guarda la configuración local en SQLite (tabla configuration).

    El token del HUB es un secreto: vive en el almacén seguro (`SecretStore`), nunca en SQLite.
    Un token en texto plano heredado de versiones anteriores se migra al leer la configuración.
    """

    def __init__(self, repository: ConfigRepository, secrets: SecretStore | None = None):
        self._repo = repository
        self._secrets = secrets if secrets is not None else InMemorySecretStore()
        self._listeners: list[Callable[[Configuration], None]] = []

    def add_listener(self, listener: Callable[[Configuration], None]) -> None:
        """Avisa a los servicios cuando se guarda la configuración."""
        self._listeners.append(listener)

    def load(self) -> Configuration:
        stored = self._repo.all()
        stored["api_token"] = self._load_token(stored.pop("api_token", ""))
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

    def _load_token(self, legacy_plaintext: str) -> str:
        """Lee el token del almacén seguro, migrando el que hubiera en texto plano en SQLite."""
        try:
            token = self._secrets.get(TOKEN_SECRET)
            if legacy_plaintext:
                if not token:
                    self._secrets.set(TOKEN_SECRET, legacy_plaintext)
                    token = legacy_plaintext
                self._repo.delete("api_token")  # solo tras haberlo guardado a salvo
                log.info("Token del HUB migrado al almacén seguro")
            return token
        except SecretStoreError as exc:
            log.error("%s", exc)
            return legacy_plaintext  # sigue en SQLite hasta poder migrarlo; no se pierde

    def save(self, config: Configuration) -> None:
        """Guarda la configuración. Lanza SecretStoreError si el token no se pudo guardar."""
        # El secreto va primero: si el almacén falla no se guarda nada a medias.
        if config.api_token != self._secrets.get(TOKEN_SECRET):
            self._secrets.set(TOKEN_SECRET, config.api_token)
        self._repo.delete("api_token")
        for key, value in asdict(config).items():
            if key != "api_token":
                self._repo.set(key, str(value))
        for listener in self._listeners:
            try:
                listener(config)
            except Exception:  # un listener defectuoso no debe impedir guardar
                log.exception("Error en listener de configuración")

    def is_terminal_configured(self) -> bool:
        cfg = self.load()
        return bool(cfg.terminal_id and cfg.hub_url)
