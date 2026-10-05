import logging
import threading
from collections.abc import Callable
from typing import Any

import websocket

from app.communication import hub_protocol as proto
from app.communication.hub_client import (
    ConnectionCallback,
    ErrorCallback,
    HubClient,
    HubConnectionError,
    TurnCallback,
)
from app.communication.hub_url import ensure_secure_url

log = logging.getLogger(__name__)

AppFactory = Callable[..., Any]  # websocket.WebSocketApp (inyectable en pruebas)


class WebSocketHubClient(HubClient):
    """Recibe turnos del HUB por WebSocket (WSS) y confirma por el mismo canal.

    El socket vive en un hilo propio; los callbacks se invocan desde ese hilo (HubService los
    reenvía al hilo de la UI). `connect()` bloquea hasta abrir o agotar el timeout, por eso
    HubService lo ejecuta fuera del hilo principal (`connect_blocks`). Cierra con la caída
    del canal o `disconnect()`; la reconexión con backoff es de HubService. La latencia de
    detección de una caída es `ping_interval` + `ping_timeout` (heartbeat de WebSocket).
    """

    connect_blocks = True

    def __init__(
        self,
        url: str,
        token: str,
        terminal_id: str,
        terminal_name: str = "",
        terminal_location: str = "",
        app_version: str = "",
        timeout: float = 10,
        ping_interval: float = 20,
        app_factory: AppFactory = websocket.WebSocketApp,
    ):
        self._url = ensure_secure_url(url, ("wss", "ws"))
        self._token = token
        self._terminal_id = terminal_id
        self._name = terminal_name
        self._location = terminal_location
        self._version = app_version
        self._timeout = timeout
        self._ping_interval = ping_interval
        self._factory = app_factory

        self._lock = threading.Lock()
        self._app: Any = None
        self._thread: threading.Thread | None = None
        self._opened = threading.Event()
        self._connected = False
        self._intentional = False
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
        self._teardown()
        self._intentional = False
        self._opened.clear()
        headers = [f"Authorization: Bearer {self._token}"] if self._token else []
        app = self._factory(
            self._url,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        thread = threading.Thread(target=self._run, args=(app,), name="hub-websocket", daemon=True)
        with self._lock:
            self._app, self._thread = app, thread
        thread.start()
        if not self._opened.wait(self._timeout) or not self._connected:
            self._teardown()
            raise HubConnectionError("No se pudo conectar al HUB (tiempo agotado o rechazado)")

    def disconnect(self) -> None:
        self._intentional = True
        self._teardown()

    def send_ack(self, message_id: str, status: str) -> None:
        self._send(proto.ack_frame(self._terminal_id, message_id, status))

    def send_ready(self) -> None:
        try:
            self._send(proto.encode(proto.T_READY, terminal_id=self._terminal_id))
        except HubConnectionError as exc:
            log.warning("READY no enviado: %s", exc)

    # --- internos --------------------------------------------------------------------------
    def _send(self, text: str) -> None:
        app = self._app
        if not self._connected or app is None:
            raise HubConnectionError("Sin conexión con el HUB")
        try:
            app.send(text)
        except (websocket.WebSocketException, OSError) as exc:
            raise HubConnectionError(f"No se pudo enviar al HUB: {exc}") from exc

    def _run(self, app: Any) -> None:
        try:
            app.run_forever(ping_interval=self._ping_interval, ping_timeout=self._ping_interval / 2)
        except Exception:  # el hilo nunca debe morir en silencio
            log.exception("Error en el hilo del WebSocket del HUB")
        self._on_close(app, None, None)

    def _teardown(self) -> None:
        with self._lock:
            app, thread = self._app, self._thread
            self._app = self._thread = None
        was_connected = self._connected
        self._connected = False
        if app is not None:
            try:
                app.close()
            except (websocket.WebSocketException, OSError) as exc:
                log.warning("Error al cerrar el WebSocket: %s", exc)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        if was_connected and self._conn_cb:
            self._conn_cb(False)

    def _on_open(self, app: Any) -> None:
        try:
            app.send(
                proto.register_frame(self._terminal_id, self._name, self._location, self._version)
            )
        except (websocket.WebSocketException, OSError) as exc:
            log.error("No se pudo registrar la terminal en el HUB: %s", exc)
            self._opened.set()  # connect() verá _connected=False
            return
        self._connected = True
        self._opened.set()
        if self._conn_cb:
            self._conn_cb(True)

    def _on_message(self, app: Any, raw: str | bytes) -> None:
        frame = proto.decode(raw)
        if frame is None:
            log.warning("Cuadro del HUB ignorado (no es JSON con 'type')")
            return
        kind = frame["type"]
        if kind == proto.T_TURN:
            payload = proto.turn_payload(frame)
            if payload is None:
                log.warning("Cuadro TURN sin 'data' válido")
            elif self._turn_cb:
                self._turn_cb(payload)
        elif kind == proto.T_PING:
            try:
                app.send(proto.encode(proto.T_PONG))
            except (websocket.WebSocketException, OSError) as exc:
                log.warning("PONG no enviado: %s", exc)
        elif kind == proto.T_ERROR:
            code, message = proto.error_info(frame)
            if self._error_cb:
                self._error_cb(code, message)
        elif kind != proto.T_REGISTERED:
            log.debug("Cuadro del HUB desconocido: %s", kind)

    def _on_error(self, app: Any, error: Exception) -> None:
        log.warning("Error del WebSocket del HUB: %s", error)

    def _on_close(self, app: Any, code: Any, reason: Any) -> None:
        was_connected = self._connected
        self._connected = False
        self._opened.set()  # libera a connect() si cerró antes de abrir
        if was_connected and not self._intentional and self._conn_cb:
            log.warning("Canal con el HUB cerrado (%s %s)", code, reason)
            self._conn_cb(False)
