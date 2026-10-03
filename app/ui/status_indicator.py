from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.controllers import app_state as st

_GREEN, _AMBER, _RED, _GREY = "#2e9e45", "#d99a00", "#c0392b", "#8a8f98"

STATUS_STYLE = {
    st.CONNECTING: ("CONECTANDO", _AMBER),
    st.CONNECTED: ("CONECTADO", _GREEN),
    st.READY: ("LISTO", _GREEN),
    st.DISCONNECTED: ("DESCONECTADO", _RED),
    st.AVAILABLE: ("DISPONIBLE", _GREEN),
    st.UNAVAILABLE: ("NO DISPONIBLE", _RED),
    st.OK: ("OK", _GREEN),
    st.ERROR: ("ERROR", _RED),
    st.UNKNOWN: ("SIN DATOS", _GREY),
}


class StatusIndicator(QWidget):
    """Fila 'NOMBRE   ● ESTADO'."""

    def __init__(self, title: str, status: str = st.UNKNOWN, parent: QWidget | None = None):
        super().__init__(parent)
        self._title = QLabel(title)
        self._title.setMinimumWidth(110)
        self._title.setStyleSheet("font-weight: 600;")
        self._value = QLabel()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.addWidget(self._title)
        layout.addWidget(self._value, 1)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        text, color = STATUS_STYLE.get(status, STATUS_STYLE[st.UNKNOWN])
        self._status = status
        self._value.setText(f"<span style='color:{color}'>●</span> {text}")

    def status(self) -> str:
        return self._status

    def text(self) -> str:
        return self._value.text()
