import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.communication.hub_client import (
    ConnectionCallback,
    ErrorCallback,
    HubClient,
    HubConnectionError,
    TurnCallback,
)


class MockHubClient(HubClient):
    """HUB simulado para desarrollar y probar sin el HUB real.

    Permite enviar turnos, duplicados, mensajes inválidos y errores, y simular caídas.
    Si el HUB "entrega" estando desconectado, el mensaje queda en cola y se entrega al reconectar.
    """

    def __init__(self, terminal_id: str = "TERM-001"):
        self.terminal_id = terminal_id
        self.reachable = True  # False = el HUB no acepta conexiones (para probar el backoff)
        self.acks: list[tuple[str, str]] = []
        self.sent: list[dict[str, Any]] = []
        self.ready_sent = 0
        self._connected = False
        self._undelivered: list[dict[str, Any]] = []
        self._turn_cb: TurnCallback | None = None
        self._conn_cb: ConnectionCallback | None = None
        self._error_cb: ErrorCallback | None = None
        self._listeners: list[Callable[[str], None]] = []

    # --- HubClient -------------------------------------------------------------------------
    def connect(self) -> None:
        if not self.reachable:
            self._log("Conexión rechazada (HUB no disponible)")
            raise HubConnectionError("HUB no disponible")
        self._connected = True
        self._log("Terminal conectada")
        self._notify_connection(True)
        self._flush_undelivered()

    def disconnect(self) -> None:
        if self._connected:
            self._connected = False
            self._log("Terminal desconectada")
            self._notify_connection(False)

    def send_ack(self, message_id: str, status: str) -> None:
        if not self._connected:
            raise HubConnectionError("Sin conexión con el HUB")
        self.acks.append((message_id, status))
        self._log(f"ACK {status}: {message_id}")

    def on_turn_received(self, callback: TurnCallback) -> None:
        self._turn_cb = callback

    def on_connection_changed(self, callback: ConnectionCallback) -> None:
        self._conn_cb = callback

    def on_error(self, callback: ErrorCallback) -> None:
        self._error_cb = callback

    def is_connected(self) -> bool:
        return self._connected

    def send_ready(self) -> None:
        self.ready_sent += 1
        self._log("Terminal READY")

    # --- Simulación (lado HUB) --------------------------------------------------------------
    def add_listener(self, listener: Callable[[str], None]) -> None:
        self._listeners.append(listener)

    def build_message(
        self,
        turn: object,
        terminal_id: str | None = None,
        message_id: str | None = None,
        priority: int = 1,
    ) -> dict[str, Any]:
        return {
            "message_id": message_id or str(uuid.uuid4()),
            "terminal_id": terminal_id or self.terminal_id,
            "turn": turn,
            "priority": priority,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "metadata": {},
        }

    def send_turn(self, turn: object, **kwargs: Any) -> dict[str, Any]:
        """Entrega un turno nuevo. Devuelve el payload enviado."""
        return self.send_payload(self.build_message(turn, **kwargs))

    def send_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Entrega un payload tal cual (permite mensajes inválidos)."""
        self.sent.append(payload)
        if self._connected:
            self._deliver(payload)
        else:
            self._undelivered.append(payload)
            self._log(f"HUB sin canal: mensaje {payload.get('message_id')} en cola")
        return payload

    def resend_last(self) -> dict[str, Any] | None:
        """Reenvía el último mensaje con el mismo message_id (duplicado)."""
        if not self.sent:
            return None
        return self.send_payload(dict(self.sent[-1]))

    def send_burst(self, first_turn: int, count: int) -> list[dict[str, Any]]:
        return [self.send_turn(first_turn + i) for i in range(count)]

    def send_invalid(self) -> dict[str, Any]:
        """Mensaje sin message_id ni turno."""
        return self.send_payload({"terminal_id": self.terminal_id})

    def send_error(self, code: str = "HUB_ERROR", message: str = "Error simulado") -> None:
        self._log(f"Error enviado: {code}")
        if self._error_cb:
            self._error_cb(code, message)

    def simulate_disconnect(self) -> None:
        """Caída inesperada de la conexión."""
        self.disconnect()

    def simulate_reconnect(self) -> None:
        """El HUB vuelve a estar disponible y la terminal se reconecta."""
        self.reachable = True
        if not self._connected:
            self.connect()

    # --- internos ---------------------------------------------------------------------------
    def _deliver(self, payload: dict[str, Any]) -> None:
        self._log(f"Turno entregado: {payload.get('turn')} ({payload.get('message_id')})")
        if self._turn_cb:
            self._turn_cb(payload)

    def _flush_undelivered(self) -> None:
        pending, self._undelivered = self._undelivered, []
        for payload in pending:
            self._deliver(payload)

    def _notify_connection(self, connected: bool) -> None:
        if self._conn_cb:
            self._conn_cb(connected)

    def _log(self, text: str) -> None:
        for listener in self._listeners:
            listener(text)
