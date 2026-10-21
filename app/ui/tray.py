from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.utils.resources import resource_path


def make_icon(color: str = "#2e9e45") -> QIcon:
    """Logo de la app con un punto de color de estado abajo a la derecha (verde/ámbar/rojo)."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    logo = QPixmap(str(resource_path("resources/icons/app.png")))
    if logo.isNull():  # sin recurso: solo el círculo de estado
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
    else:
        painter.drawPixmap(
            0,
            0,
            logo.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        )
        painter.setBrush(QColor(color))
        painter.setPen(QPen(QColor("#FFFFFF"), 4))
        painter.drawEllipse(34, 34, 28, 28)
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
