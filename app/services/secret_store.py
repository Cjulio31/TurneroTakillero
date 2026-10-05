import logging
from typing import Protocol

import keyring
from keyring.errors import KeyringError

from app.services.errors import SecretStoreError

log = logging.getLogger(__name__)

KEYRING_SERVICE = "TurnosDesktop"


class SecretStore(Protocol):
    def get(self, name: str) -> str:
        """Devuelve el secreto ('' si no existe). Lanza SecretStoreError si el almacén falla."""

    def set(self, name: str, value: str) -> None:
        """Guarda el secreto; un valor vacío lo elimina. Lanza SecretStoreError si falla."""


class KeyringSecretStore:
    """Almacén del sistema: Windows Credential Manager (DPAPI), Keychain o Secret Service."""

    def __init__(self, service: str = KEYRING_SERVICE):
        self._service = service

    def get(self, name: str) -> str:
        try:
            return keyring.get_password(self._service, name) or ""
        except KeyringError as exc:
            raise SecretStoreError(f"No se pudo leer '{name}' del almacén: {exc}") from exc

    def set(self, name: str, value: str) -> None:
        try:
            if value:
                keyring.set_password(self._service, name, value)
            elif keyring.get_password(self._service, name) is not None:
                keyring.delete_password(self._service, name)
        except KeyringError as exc:
            raise SecretStoreError(f"No se pudo guardar '{name}' en el almacén: {exc}") from exc


class InMemorySecretStore:
    """Solo para pruebas: no persiste nada."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, name: str) -> str:
        return self._data.get(name, "")

    def set(self, name: str, value: str) -> None:
        if value:
            self._data[name] = value
        else:
            self._data.pop(name, None)
