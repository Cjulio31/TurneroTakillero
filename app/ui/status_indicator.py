from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.controllers import app_state as st
from app.ui import icons
from app.ui.theme import LEVEL_ICON, state_level, theme
from app.ui.widgets import IconBox

_GREEN, _AMBER, _RED, _GREY = "#2e9e45", "#d99a00", "#c0392b", "#8a8f98"

# (texto, color): el color solo lo usa el ícono de la bandeja; la UI colorea por nivel (theme).
STATUS_STYLE = {
    st.CONNECTING: ("CONECTANDO", _AMBER),
    st.CONNECTED: ("CONECTADO", _GREEN),
    st.READY: ("LISTO", _GREEN),
    st.DISCONNECTED: ("DESCONECTADO", _RED),
    st.AVAILABLE: ("DISPONIBLE", _GREEN),
    st.UNAVAILABLE: ("NO DISPONIBLE", _RED),
    st.DISABLED: ("DESACTIVADA", _GREY),
    st.OK: ("OK", _GREEN),
    st.ERROR: ("ERROR", _RED),
    st.UNKNOWN: ("SIN DATOS", _GREY),
}


class StatusIndicator(QFrame):
    """Tarjeta de estado de un componente: ícono, nombre, glifo + estado y un detalle opcional.

    El estado se comunica con color **y** glifo (✔ ⚠ ✖), no solo con color.
    """

    def __init__(
        self,
        title: str,
        status: str = st.UNKNOWN,
        icon: str = "chip",
        detail: str = "",
        compact: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("StatusCard")
        self._status = status
        self._compact = compact
        self._box = IconBox(icon, 34 if compact else 38)
        self._title = QLabel(title.upper())
        self._title.setObjectName("CardCaption")
        self._glyph = QLabel()
        self._value = QLabel()
        self._detail = QLabel(detail)
        self._detail.setObjectName("Hint")
        self._detail.setVisible(bool(detail) and not compact)

        state_row = QHBoxLayout()
        state_row.setContentsMargins(0, 0, 0, 0)
        state_row.setSpacing(6)
        state_row.addWidget(self._glyph)
        state_row.addWidget(self._value)
        state_row.addStretch(1)

        if compact:
            text = QVBoxLayout()
            text.setSpacing(0)
            text.addWidget(self._title)
            text.addLayout(state_row)
            layout = QHBoxLayout(self)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(10)
            layout.addWidget(self._box)
            layout.addLayout(text, 1)
        else:
            head = QHBoxLayout()
            head.setSpacing(10)
            head.addWidget(self._box)
            head.addWidget(self._title, 1)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(6)
            layout.addLayout(head)
            layout.addStretch(1)
            layout.addLayout(state_row)
            layout.addWidget(self._detail)
        theme.changed.connect(self._refresh)
        self._refresh()

    def set_status(self, status: str) -> None:
        self._status = status
        self._refresh()

    def set_detail(self, detail: str) -> None:
        self._detail.setText(detail)
        self._detail.setVisible(bool(detail) and not self._compact)

    def status(self) -> str:
        return self._status

    def text(self) -> str:
        return self._value.text()

    def _refresh(self, *_: object) -> None:
        p = theme.palette
        level = state_level(self._status)
        text = STATUS_STYLE.get(self._status, STATUS_STYLE[st.UNKNOWN])[0]
        err = level == "err"
        bg, border = (p.err_card, p.err_border) if err else (p.surface, p.border)
        radius = 14 if self._compact else 16
        self.setStyleSheet(
            f"QFrame#StatusCard {{ background: {bg}; border: 1px solid {border}; "
            f"border-radius: {radius}px; }}"
        )
        self._box.set_level(level)
        self._value.setText(text)
        self._value.setStyleSheet(
            f"font-size: {14 if self._compact else 20}px; font-weight: 800; "
            f"color: {p.fg(level)}; background: transparent;"
        )
        size = 14 if self._compact else 20
        self._glyph.setStyleSheet("background: transparent;")
        self._glyph.setPixmap(icons.pixmap(LEVEL_ICON[level], p.fg(level), size, 2.6))
        self._glyph.setAlignment(Qt.AlignmentFlag.AlignVCenter)
