from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def make_icon(color: str = "#2e9e45") -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)


class TrayController(QObject):
    """Icono de bandeja: Abrir / Estado / Configuración / Salir."""

    open_requested = Signal()
    configuration_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self.icon = QSystemTrayIcon(make_icon(), self)
        menu = QMenu()
        menu.addAction("Abrir").triggered.connect(self.open_requested)
        self.status_action = QAction("Estado: iniciando", menu)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        menu.addAction("Configuración").triggered.connect(self.configuration_requested)
        menu.addSeparator()
        menu.addAction("Salir").triggered.connect(self.quit_requested)
        self._menu = menu
        self.icon.setContextMenu(menu)
        self.icon.setToolTip("Turnos")
        self.icon.activated.connect(self._on_activated)
        if self.available:
            self.icon.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_requested.emit()

    def set_status_text(self, text: str, color: str = "#2e9e45") -> None:
        self.status_action.setText(f"Estado: {text}")
        self.icon.setIcon(make_icon(color))
        self.icon.setToolTip(f"Turnos — {text}")
