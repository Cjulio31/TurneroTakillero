import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

import serial
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from app.communication.backoff import BackoffPolicy
from app.controllers import app_state as st
from app.controllers.app_state import AppState
from app.database.event_repository import EventRepository
from app.hardware.serial_device import SerialDevice, SerialSettings, list_serial_ports
from app.protocol.turn_protocol import TurnProtocol
from app.services.errors import SerialSendError, SerialUnavailableError
from app.utils import constants

log = logging.getLogger(__name__)

SERIAL_BACKOFF = (2, 5, 10, 20, 30)  # segundos entre intentos de reconexión
HEALTH_INTERVAL_MS = 3000

DeviceFactory = Callable[[SerialSettings], SerialDevice]


@dataclass
class SerialStatus:
    connected: bool
    port: str
    error: str


class _ConnectTask(QRunnable):
    """Abre el puerto fuera del hilo de la UI (abrir un COM puede tardar)."""

    def __init__(self, service: "SerialService", settings: SerialSettings):
        super().__init__()
        self._service = service
        self._settings = settings

    def run(self) -> None:
        device, error = None, ""
        try:
            device = self._service._factory(self._settings)
        except (serial.SerialException, OSError, ValueError) as exc:
            error = str(exc)
        self._service._connect_done.emit(self._settings, device, error)


class SerialService(QObject):
    """Comunicación serial: conexión, reconexión automática y envío de turnos.

    - Sin puerto o con el puerto caído: SerialUnavailableError (nada enviado, reintento seguro).
    - Falla durante la escritura: SerialSendError (resultado incierto, sin ACK).
    """

    connection_changed = Signal(bool)
    _connect_done = Signal(object, object, str)

    def __init__(
        self,
        state: AppState,
        events: EventRepository,
        settings_provider: Callable[[], SerialSettings],
        device_factory: DeviceFactory = SerialDevice.open,
        port_lister: Callable[[], list[str]] = list_serial_ports,
        backoff: BackoffPolicy | None = None,
        protocol: TurnProtocol | None = None,
        health_interval_ms: int = HEALTH_INTERVAL_MS,
    ):
        super().__init__()
        self._state = state
        self._events = events
        self._provider = settings_provider
        self._factory = device_factory
        self._list_ports = port_lister
        self._backoff = backoff or BackoffPolicy(SERIAL_BACKOFF)
        self._protocol = protocol or TurnProtocol()

        self._lock = threading.Lock()
        self._device: SerialDevice | None = None
        self._active: SerialSettings | None = None
        self._port_was_listed = False
        self._running = False
        self._connecting = False
        self._last_error = ""

        self._connect_done.connect(self._on_connect_done)
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._begin_connect)
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(health_interval_ms)
        self._health_timer.timeout.connect(self._check_alive)

    # --- ciclo de vida ---------------------------------------------------------------------
    def start(self) -> None:
        self._running = True
        self._health_timer.start()
        self._begin_connect()

    def stop(self) -> None:
        self._running = False
        self._retry_timer.stop()
        self._health_timer.stop()
        self._close_device()
        self._state.set_status("serial", st.DISCONNECTED)

    def connect(self) -> bool:
        """Conexión síncrona (diagnóstico y pruebas). La reconexión automática es asíncrona."""
        settings = self._provider()
        device, error = None, ""
        if not settings.port:
            error = "Puerto serial no configurado"
        else:
            try:
                device = self._factory(settings)
            except (serial.SerialException, OSError, ValueError) as exc:
                error = str(exc)
        self._on_connect_done(settings, device, error)
        return self.is_connected()

    def disconnect(self) -> None:
        self._close_device()
        self._state.set_status("serial", st.DISCONNECTED)
        self.connection_changed.emit(False)

    def reconnect(self) -> None:
        """Cierra el puerto (si está abierto) y reintenta de inmediato."""
        self._retry_timer.stop()
        self._backoff.reset()
        self._close_device()
        self._begin_connect()

    def on_config_changed(self) -> None:
        """Reabre el puerto solo si cambió algún parámetro de conexión."""
        if not self._running:
            return
        current = self._provider().connection_key
        if self._active is None or current != self._active.connection_key:
            self.reconnect()

    # --- estado ----------------------------------------------------------------------------
    def is_connected(self) -> bool:
        with self._lock:
            return self._device is not None and self._device.is_open

    @property
    def transmissions(self) -> int:
        return max(1, self._provider().transmissions)

    def get_status(self) -> SerialStatus:
        settings = self._active or self._provider()
        return SerialStatus(self.is_connected(), settings.port, self._last_error)

    # --- envío -----------------------------------------------------------------------------
    def send_turn(self, turn_number: int) -> None:
        packet = self._protocol.build_packet(turn_number)
        self._ensure_port_present()
        for _ in range(self.transmissions):
            self.send(packet)

    def send(self, data: bytes) -> None:
        with self._lock:
            device = self._device
            if device is None or not device.is_open:
                raise SerialUnavailableError(self._last_error or "Serial desconectado")
            try:
                written = device.write(data)
                if written is not None and written != len(data):
                    raise serial.SerialException(f"Escritura parcial: {written}/{len(data)} bytes")
            except (serial.SerialException, OSError) as exc:
                failure = exc
            else:
                failure = None
        if failure is not None:
            log.error("SERIAL TX failed (%s): %s", self._protocol.format_packet(data), failure)
            self._handle_lost(f"Error al escribir: {failure}")
            raise SerialSendError(str(failure)) from failure
        log.info("SERIAL TX: %s", self._protocol.format_packet(data))

    # --- conexión interna ------------------------------------------------------------------
    def _begin_connect(self) -> None:
        if not self._running or self._connecting or self.is_connected():
            return
        settings = self._provider()
        if not settings.port:
            self._connection_failed("Puerto serial no configurado")
            return
        self._connecting = True
        self._state.set_status("serial", st.CONNECTING)
        QThreadPool.globalInstance().start(_ConnectTask(self, settings))

    def _on_connect_done(
        self, settings: SerialSettings, device: SerialDevice | None, error: str
    ) -> None:
        self._connecting = False
        if device is not None and settings.connection_key != self._provider().connection_key:
            # la configuración cambió mientras se abría el puerto: se descarta y se reintenta
            self._safe_close(device)
            if self._running:
                self._begin_connect()
                return
            device, error = None, "Configuración modificada durante la conexión"
        if device is None:
            self._connection_failed(error)
            return
        with self._lock:
            self._device = device
            self._active = settings
        self._port_was_listed = self._is_listed(settings.port)
        self._backoff.reset()
        self._last_error = ""
        self._state.set_status("serial", st.CONNECTED)
        self._events.add(constants.EVENT_SERIAL_CONNECTED, f"Serial conectado en {settings.port}")
        log.info("SERIAL connected: %s @ %s", settings.port, settings.baudrate)
        self.connection_changed.emit(True)

    def _connection_failed(self, error: str) -> None:
        first_failure = error != self._last_error
        self._last_error = error
        self._state.set_status("serial", st.DISCONNECTED)
        if first_failure:  # evita llenar el log/eventos en cada reintento
            log.warning("SERIAL no disponible: %s", error)
            self._events.add(constants.EVENT_SERIAL_ERROR, error)
        self._schedule_retry()

    def _schedule_retry(self) -> None:
        if self._running and not self._retry_timer.isActive():
            self._retry_timer.start(int(self._backoff.next_delay() * 1000))

    def _handle_lost(self, reason: str) -> None:
        """El puerto se perdió estando conectado: se cierra y se programa la reconexión."""
        was_connected = self.is_connected()
        self._close_device()
        self._last_error = reason
        self._state.set_status("serial", st.DISCONNECTED)
        self._events.add(constants.EVENT_SERIAL_ERROR, reason)
        log.error("SERIAL lost: %s", reason)
        if was_connected:
            self.connection_changed.emit(False)
        self._schedule_retry()

    def _check_alive(self) -> None:
        if self.is_connected() and not self._port_present():
            self._handle_lost("Puerto serial desconectado")

    def _ensure_port_present(self) -> None:
        """Si el puerto desapareció, nada se envía: el turno queda pendiente (reintento seguro)."""
        if self.is_connected() and not self._port_present():
            self._handle_lost("Puerto serial desconectado")
            raise SerialUnavailableError(self._last_error)

    def _port_present(self) -> bool:
        port = self._active.port if self._active else ""
        # URLs (loop://, socket://) y puertos virtuales que nunca se listaron no se pueden verificar
        if not port or "://" in port or not self._port_was_listed:
            return True
        return self._is_listed(port)

    def _is_listed(self, port: str) -> bool:
        try:
            return port.casefold() in {p.casefold() for p in self._list_ports()}
        except OSError as exc:
            log.warning("No se pudo listar los puertos: %s", exc)
            return True

    def _close_device(self) -> None:
        with self._lock:
            device, self._device = self._device, None
            self._active = None if device is None else self._active
        if device is not None:
            self._safe_close(device)

    @staticmethod
    def _safe_close(device: SerialDevice) -> None:
        try:
            device.close()
        except (serial.SerialException, OSError) as exc:
            log.warning("Error al cerrar el puerto serial: %s", exc)
