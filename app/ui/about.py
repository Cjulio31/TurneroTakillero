from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui import icons
from app.ui.theme import theme
from app.ui.widgets import bind_icon, caption, card, header_row
from app.utils import constants

DESCRIPTION = (
    "Terminal de turnos: recibe turnos desde el HUB/HOOB, los guarda localmente, "
    "los envía al dispositivo serial y los imprime."
)


class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")
        header, _ = header_row("Acerca de", "Versión e información del equipo")

        self._mark = QLabel()
        self._mark.setFixedSize(68, 68)
        title = QLabel(constants.APP_NAME)
        title.setStyleSheet("font-size: 26px; font-weight: 800; background: transparent;")
        version = QLabel(f"Versión {constants.APP_VERSION}")
        version.setProperty("mono", True)
        version.setObjectName("Hint")
        brand_text = QVBoxLayout()
        brand_text.setSpacing(4)
        brand_text.addWidget(title)
        brand_text.addWidget(version)
        brand = QHBoxLayout()
        brand.setSpacing(18)
        brand.addWidget(self._mark)
        brand.addLayout(brand_text)
        brand.addStretch(1)

        description = QLabel(DESCRIPTION)
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 15px; background: transparent;")

        rows = QFrame()
        rows.setObjectName("Dashed")
        rows_layout = QVBoxLayout(rows)
        rows_layout.setContentsMargins(18, 8, 18, 8)
        rows_layout.setSpacing(0)
        for label, value in (
            ("Datos en", str(constants.BASE_DIR)),
            ("Base de datos", str(constants.DATABASE_PATH)),
            ("Registros", str(constants.LOG_PATH)),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 8, 0, 8)
            row.addWidget(caption(label))
            row.addStretch(1)
            text = QLabel(value)
            text.setProperty("mono", True)
            text.setStyleSheet("font-size: 12px; background: transparent;")
            text.setWordWrap(True)
            text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(text, 3)
            rows_layout.addLayout(row)

        open_data = QPushButton("Abrir carpeta de datos")
        open_data.setProperty("primary", True)
        open_data.clicked.connect(self.open_data_folder)
        bind_icon(open_data, "folder", "on_accent")
        copy = QPushButton("Copiar información")
        copy.clicked.connect(self.copy_info)
        bind_icon(copy, "copy", "text2")
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addWidget(open_data)
        buttons.addWidget(copy)
        buttons.addStretch(1)

        panel = card()
        panel.setMaximumWidth(680)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(32, 30, 32, 30)
        panel_layout.setSpacing(22)
        panel_layout.addLayout(brand)
        panel_layout.addWidget(description)
        panel_layout.addWidget(rows)
        panel_layout.addLayout(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)
        layout.addLayout(header)
        layout.addWidget(panel)
        layout.addStretch(1)
        theme.changed.connect(self._refresh_mark)
        self._refresh_mark()

    def _refresh_mark(self, *_: object) -> None:
        p = theme.palette
        self._mark.setStyleSheet(f"background: {p.accent_soft}; border-radius: 20px;")
        self._mark.setPixmap(icons.pixmap("ticket", p.accent, 38, 1.7))
        self._mark.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def info_text(self) -> str:
        return (
            f"{constants.APP_NAME} {constants.APP_VERSION}\n"
            f"Datos: {constants.BASE_DIR}\n"
            f"Base de datos: {constants.DATABASE_PATH}\n"
            f"Registros: {constants.LOG_PATH}"
        )

    def open_data_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(constants.BASE_DIR)))

    def copy_info(self) -> None:
        QApplication.clipboard().setText(self.info_text())
