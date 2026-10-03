from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

# Un mensaje del HUB llega crudo (dict); TurnService lo valida y lo convierte a TurnMessage.
TurnCallback = Callable[[dict[str, Any]], None]
ConnectionCallback = Callable[[bool], None]
ErrorCallback = Callable[[str, str], None]  # (código, mensaje)


class HubConnectionError(Exception):
    """No se pudo conectar o enviar al HUB."""


class HubClient(ABC):
    """Contrato común de todos los transportes (Mock, WebSocket, REST).

    TurnService/HubService solo conocen esta interfaz: cambiar de tecnología no los afecta.
    """

    @abstractmethod
    def connect(self) -> None:
        """Conecta y registra la terminal. Lanza HubConnectionError si falla."""

    @abstractmethod
    def disconnect(self) -> None:
        """Cierra la conexión de forma intencional."""

    @abstractmethod
    def send_ack(self, message_id: str, status: str) -> None:
        """Confirma al HUB el resultado de un mensaje. Lanza HubConnectionError si no hay canal."""

    @abstractmethod
    def on_turn_received(self, callback: TurnCallback) -> None:
        """Registra quién recibe los mensajes de turno (payload crudo)."""

    @abstractmethod
    def is_connected(self) -> bool: ...

    def on_connection_changed(self, callback: ConnectionCallback) -> None:  # noqa: B027
        """Notifica pérdidas/recuperaciones de conexión. Opcional para transportes sin eventos."""

    def on_error(self, callback: ErrorCallback) -> None:  # noqa: B027
        """Notifica errores enviados por el HUB. Opcional."""

    def send_ready(self) -> None:  # noqa: B027
        """Informa al HUB que la terminal está lista para recibir turnos. Opcional."""
