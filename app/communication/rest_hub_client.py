import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.communication.hub_client import (
    ConnectionCallback,
    ErrorCallback,
    HubClient,
    HubConnectionError,
    TurnCallback,
)
from app.communication.hub_url import ensure_secure_url

log = logging.getLogger(__name__)


class RestHubClient(HubClient):
    """Transporte REST: registro, consulta periódica de turnos (polling) y confirmaciones.

    PROVISIONAL (ver docs/HUB_PROTOCOLO.md), rutas relativas a la URL base:

    - ``POST   /terminals/{id}/register``   registra la terminal.
    - ``GET    /terminals/{id}/messages``   lista de mensajes pendientes (JSON, lista).
    - ``POST   /messages/{message_id}/ack`` ``{"terminal_id", "status"}``.

    Un mensaje puede llegar más de una vez hasta que se confirma: es seguro porque TurnService
    es idempotente por ``message_id``. Si una consulta falla se considera caída la conexión y
    HubService reconecta con backoff.
    """

    connect_blocks = True

    def __init__(
        self,
        base_url: str,
        token: str,
        terminal_id: str,
        terminal_name: str = "",
        terminal_location: str = "",
        app_version: str = "",
        timeout: float = 10,
        poll_interval: float = 3,
    ):
        self._base = ensure_secure_url(base_url, ("https", "http")).rstrip("/")
        self._token = token
        self._terminal_id = terminal_id
        self._name = terminal_name
        self._location = terminal_location
        self._version = app_version
        self._timeout = timeout
        self._poll_interval = poll_interval

        self._connected = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._turn_cb: TurnCallback | None = None
        self._conn_cb: ConnectionCallback | None = None
        self._error_cb: ErrorCallback | None = None

    # --- HubClient -------------------------------------------------------------------------
    def on_turn_received(self, callback: TurnCallback) -> None:
        self._turn_cb = callback

    def on_connection_changed(self, callback: ConnectionCallback) -> None:
        self._conn_cb = callback

    def on_error(self, callback: ErrorCallback) -> None:
        self._error_cb = callback

    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        if self._connected:
            return
        self._join()
        self._request(
            "POST",
            f"/terminals/{self._quoted_terminal()}/register",
            {
                "terminal_id": self._terminal_id,
                "name": self._name,
                "location": self._location,
                "app_version": self._version,
            },
        )
        self._stop.clear()
        self._connected = True
        self._thread = threading.Thread(target=self._poll, name="hub-rest", daemon=True)
        self._thread.start()
        if self._conn_cb:
            self._conn_cb(True)

    def disconnect(self) -> None:
        was_connected = self._connected
        self._connected = False
        self._join()
        if was_connected and self._conn_cb:
            self._conn_cb(False)

    def send_ack(self, message_id: str, status: str) -> None:
        if not self._connected:
            raise HubConnectionError("Sin conexión con el HUB")
        quoted = urllib.parse.quote(message_id, safe="")
        self._request(
            "POST",
            f"/messages/{quoted}/ack",
            {"terminal_id": self._terminal_id, "status": status},
        )

    # --- internos --------------------------------------------------------------------------
    def _quoted_terminal(self) -> str:
        return urllib.parse.quote(self._terminal_id, safe="")

    def _join(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=self._timeout + 1)

    def _poll(self) -> None:
        path = f"/terminals/{self._quoted_terminal()}/messages"
        while not self._stop.wait(self._poll_interval):
            try:
                messages = self._request("GET", path)
            except HubConnectionError as exc:
                log.warning("Consulta de turnos al HUB falló: %s", exc)
                self._lost()
                return
            if not isinstance(messages, list):
                log.warning("El HUB devolvió un cuerpo inesperado (se esperaba una lista)")
                continue
            for message in messages:
                if isinstance(message, dict) and self._turn_cb:
                    self._turn_cb(message)

    def _lost(self) -> None:
        was_connected, self._connected = self._connected, False
        if was_connected and self._conn_cb:
            self._conn_cb(False)

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self._base + path, data=data, method=method)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if self._token:
            request.add_header("Authorization", f"Bearer {self._token}")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise HubConnectionError("Autenticación rechazada por el HUB") from exc
            raise HubConnectionError(f"El HUB respondió HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise HubConnectionError(f"No se pudo contactar al HUB: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise HubConnectionError("Respuesta del HUB no es JSON") from exc
