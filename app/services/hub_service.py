import logging
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from app.communication.backoff import BackoffPolicy
from app.communication.hub_client import HubClient, HubConnectionError
from app.controllers import app_state as st
from app.controllers.app_state import AppState
from app.database.event_repository import EventRepository
from app.utils import constants

log = logging.getLogger(__name__)


class _ConnectTask(QRunnable):
    """connect() de un transporte de red, fuera del hilo de la UI."""

    def __init__(self, service: "HubService"):
        super().__init__()
        self._service = service

    def run(self) -> None:
        error = ""
        try:
            self._service._client.connect()
        except HubConnectionError as exc:
            error = str(exc)
        except Exception as exc:  # un transporte defectuoso no debe dejar la app sin reintentos
            log.exception("Error inesperado al conectar con el HUB")
            error = str(exc)
        self._service._connect_done.emit(error)


class HubService(QObject):
    """Mantiene la conexión con el HUB: conecta, reconecta con backoff y reenvía los turnos.

    No conoce el transporte (usa HubClient) ni procesa turnos (eso es TurnService).
    """

    turn_received = Signal(dict)  # payload crudo, sin validar
    hub_error = Signal(str, str)  # código, mensaje
    # Los transportes de red llaman a los callbacks desde sus hilos: estas señales los llevan
    # (en cola) al hilo de la UI. Con el mock (mismo hilo) se ejecutan de inmediato.
    _turn_signal = Signal(dict)
    _connection_signal = Signal(bool)
    _error_signal = Signal(str, str)
    _connect_done = Signal(str)

    def __init__(
        self,
        client: HubClient,
        state: AppState,
        events: EventRepository,
        backoff: BackoffPolicy | None = None,
    ):
        super().__init__()
        self._client = client
        self._state = state
        self._events = events
        self._backoff = backoff or BackoffPolicy()
        self._running = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._attempt_connect)
        self._connecting = False
        self._turn_signal.connect(self._on_turn)
        self._connection_signal.connect(self._on_connection_changed)
        self._error_signal.connect(self._on_error)
        self._connect_done.connect(self._on_connect_done)
        client.on_turn_received(self._turn_signal.emit)
        client.on_connection_changed(self._connection_signal.emit)
        client.on_error(self._error_signal.emit)

    @property
    def client(self) -> HubClient:
        return self._client

    @property
    def backoff(self) -> BackoffPolicy:
        return self._backoff

    def start(self) -> None:
        self._running = True
        self._attempt_connect()

    def stop(self) -> None:
        self._running = False
        self._timer.stop()
        self._client.disconnect()
        self._state.set_status("hub", st.DISCONNECTED)

    def reconnect_now(self) -> None:
        """Reintenta de inmediato (prueba de diagnóstico), sin esperar el backoff."""
        if not self._running or self._client.is_connected():
            return
        self._timer.stop()
        self._backoff.reset()
        self._attempt_connect()

    def send_ack(self, message_id: str, status: str) -> bool:
        """Confirma un mensaje al HUB. False si no hay canal (queda para la sincronización)."""
        try:
            self._client.send_ack(message_id, status)
        except HubConnectionError as exc:
            log.warning("ACK %s (%s) no enviado: %s", message_id, status, exc)
            return False
        return True

    def _attempt_connect(self) -> None:
        if not self._running or self._connecting or self._client.is_connected():
            return
        self._state.set_status("hub", st.CONNECTING)
        if self._client.connect_blocks:
            self._connecting = True
            QThreadPool.globalInstance().start(_ConnectTask(self))
            return
        try:
            self._client.connect()
        except HubConnectionError as exc:
            self._connect_failed(str(exc))

    def _on_connect_done(self, error: str) -> None:
        self._connecting = False
        if error:
            self._connect_failed(error)
        elif not self._running:  # se detuvo mientras conectaba
            self._client.disconnect()

    def _connect_failed(self, error: str) -> None:
        log.warning("No se pudo conectar al HUB: %s", error)
        self._state.set_status("hub", st.DISCONNECTED)
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if not self._running or self._timer.isActive():
            return
        delay = self._backoff.next_delay()
        log.info("Reintentando conexión al HUB en %s s", delay)
        self._timer.start(int(delay * 1000))

    def _on_connection_changed(self, connected: bool) -> None:
        if connected:
            self._backoff.reset()
            self._timer.stop()
            self._state.set_status("hub", st.CONNECTED)
            self._events.add(constants.EVENT_HUB_CONNECTED, "HUB conectado")
            log.info("HUB connected")
            self._client.send_ready()
            self._state.set_status("hub", st.READY)
        else:
            self._state.set_status("hub", st.DISCONNECTED)
            self._events.add(constants.EVENT_HUB_DISCONNECTED, "HUB desconectado")
            log.warning("HUB disconnected")
            self._schedule_reconnect()

    def _on_turn(self, payload: dict[str, Any]) -> None:
        log.info("HUB message received: %s", payload.get("message_id"))
        self.turn_received.emit(payload)

    def _on_error(self, code: str, message: str) -> None:
        log.error("HUB error %s: %s", code, message)
        self._events.add("HUB_ERROR", f"{code}: {message}")
        self.hub_error.emit(code, message)
