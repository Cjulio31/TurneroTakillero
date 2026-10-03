from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.utils import constants


class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        label = QLabel(
            f"<h2>{constants.APP_NAME}</h2>"
            f"<p>Versión {constants.APP_VERSION}</p>"
            "<p>Terminal de turnos: recibe turnos desde el HUB/HOOB, los guarda localmente, "
            "los envía al dispositivo serial y los imprime.</p>"
            f"<p>Datos en: {constants.BASE_DIR}</p>"
        )
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addStretch(1)
