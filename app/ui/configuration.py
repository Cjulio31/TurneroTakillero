from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controllers.config_controller import ConfigController
from app.services.errors import SecretStoreError
from app.ui.status_indicator import StatusIndicator


class ConfigurationPage(QWidget):
    """Configuración del HUB y de la terminal."""

    def __init__(
        self, controller: ConfigController, hub_status: str, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self._controller = controller

        self.hub_url = QLineEdit()
        self.hub_url.setPlaceholderText("https://hub.midominio.com")
        self.terminal_id = QLineEdit()
        self.terminal_id.setPlaceholderText("TERM-001")
        self.terminal_name = QLineEdit()
        self.terminal_location = QLineEdit()
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.timeout = QSpinBox()
        self.timeout.setRange(1, 300)
        self.timeout.setSuffix(" s")
        self.reconnect = QSpinBox()
        self.reconnect.setRange(1, 60)
        self.reconnect.setSuffix(" s")

        hub = QGroupBox("HUB")
        form = QFormLayout(hub)
        form.addRow("URL HUB", self.hub_url)
        form.addRow("Token / API Key", self.token)
        form.addRow("Timeout", self.timeout)
        form.addRow("Intervalo de reconexión", self.reconnect)
        self.hub_indicator = StatusIndicator("Estado", hub_status)
        form.addRow(self.hub_indicator)

        terminal = QGroupBox("Terminal")
        tform = QFormLayout(terminal)
        tform.addRow("Terminal ID", self.terminal_id)
        tform.addRow("Nombre", self.terminal_name)
        tform.addRow("Ubicación", self.terminal_location)

        save = QPushButton("Guardar")
        save.clicked.connect(self.save)
        self.message = QLabel()

        layout = QVBoxLayout(self)
        layout.addWidget(hub)
        layout.addWidget(terminal)
        layout.addWidget(save)
        layout.addWidget(self.message)
        layout.addStretch(1)
        self.load()

    def load(self) -> None:
        cfg = self._controller.load()
        self.hub_url.setText(cfg.hub_url)
        self.token.setText(cfg.api_token)
        self.timeout.setValue(cfg.hub_timeout)
        self.reconnect.setValue(cfg.reconnect_interval)
        self.terminal_id.setText(cfg.terminal_id)
        self.terminal_name.setText(cfg.terminal_name)
        self.terminal_location.setText(cfg.terminal_location)

    def save(self, msg_box: bool = True) -> bool:
        try:
            self._controller.update(
                hub_url=self.hub_url.text().strip(),
                api_token=self.token.text(),
                hub_timeout=self.timeout.value(),
                reconnect_interval=self.reconnect.value(),
                terminal_id=self.terminal_id.text().strip(),
                terminal_name=self.terminal_name.text().strip(),
                terminal_location=self.terminal_location.text().strip(),
            )
        except (ValueError, SecretStoreError) as exc:
            self.message.setText(f"No guardado: {exc}")
            if msg_box:
                QMessageBox.warning(self, "Configuración", str(exc))
            return False
        self.message.setText("Configuración guardada. Se aplicará al reconectar.")
        return True
