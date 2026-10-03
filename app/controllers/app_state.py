from PySide6.QtCore import QObject, Signal

# Estados de conexión/disponibilidad que muestran los indicadores de la UI.
CONNECTING = "CONNECTING"
CONNECTED = "CONNECTED"
READY = "READY"
DISCONNECTED = "DISCONNECTED"
AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"
OK = "OK"
ERROR = "ERROR"
UNKNOWN = "UNKNOWN"

COMPONENTS = ("hub", "serial", "printer", "database")


class AppState(QObject):
    """Estado compartido que los servicios (fases 3-7) actualizan y la UI observa."""

    status_changed = Signal(str, str)  # componente, estado
    last_times_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._status = dict.fromkeys(COMPONENTS, UNKNOWN)
        self.last_received: str | None = None
        self.last_printed: str | None = None

    def status(self, component: str) -> str:
        return self._status[component]

    def set_status(self, component: str, status: str) -> None:
        if component not in self._status:
            raise KeyError(component)
        if self._status[component] != status:
            self._status[component] = status
            self.status_changed.emit(component, status)

    def set_last_times(self, received: str | None = None, printed: str | None = None) -> None:
        if received:
            self.last_received = received
        if printed:
            self.last_printed = printed
        self.last_times_changed.emit()
