from datetime import datetime

from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.communication.mock_hub_client import MockHubClient


class MockHubPage(QWidget):
    """Panel de control del HUB simulado (solo visible cuando se usa MockHubClient)."""

    def __init__(self, mock: MockHubClient, parent: QWidget | None = None):
        super().__init__(parent)
        self._mock = mock

        self.terminal = QLineEdit(mock.terminal_id)
        self.turn = QSpinBox()
        self.turn.setRange(0, 999)
        self.turn.setValue(25)
        self.count = QSpinBox()
        self.count.setRange(2, 50)
        self.count.setValue(5)
        self.reachable = QCheckBox("HUB disponible (aceptar conexiones)")
        self.reachable.setChecked(mock.reachable)
        self.reachable.toggled.connect(self._set_reachable)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        actions = (
            ("ENVIAR", self._send),
            ("REENVIAR (duplicado)", self._resend),
            ("ENVIAR VARIOS", self._burst),
            ("MENSAJE INVÁLIDO", self._invalid),
            ("ERROR", self._error),
            ("DESCONECTAR", self._disconnect),
            ("RECONECTAR", self._reconnect),
        )
        box = QGroupBox("MOCK HUB")
        grid = QGridLayout(box)
        grid.addWidget(QLabel("Terminal destino"), 0, 0)
        grid.addWidget(self.terminal, 0, 1)
        grid.addWidget(QLabel("Turno"), 1, 0)
        grid.addWidget(self.turn, 1, 1)
        grid.addWidget(QLabel("Cantidad (varios)"), 2, 0)
        grid.addWidget(self.count, 2, 1)
        self.buttons: dict[str, QPushButton] = {}
        for i, (text, handler) in enumerate(actions):
            button = QPushButton(text)
            button.clicked.connect(handler)
            self.buttons[text] = button
            grid.addWidget(button, 3 + i // 2, i % 2)
        grid.addWidget(self.reachable, 7, 0, 1, 2)

        layout = QVBoxLayout(self)
        layout.addWidget(box)
        layout.addWidget(self.log, 1)
        mock.add_listener(self._append_log)

    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(f"{datetime.now():%H:%M:%S}  {text}")

    def _sync_terminal(self) -> None:
        self._mock.terminal_id = self.terminal.text().strip()

    def _send(self) -> None:
        self._sync_terminal()
        self._mock.send_turn(self.turn.value())

    def _resend(self) -> None:
        if self._mock.resend_last() is None:
            self._append_log("No hay mensajes previos para reenviar")

    def _burst(self) -> None:
        self._sync_terminal()
        self._mock.send_burst(self.turn.value(), self.count.value())

    def _invalid(self) -> None:
        self._sync_terminal()
        self._mock.send_invalid()

    def _error(self) -> None:
        self._mock.send_error()

    def _disconnect(self) -> None:
        self._mock.simulate_disconnect()

    def _reconnect(self) -> None:
        self.reachable.setChecked(True)
        self._mock.simulate_reconnect()

    def _set_reachable(self, value: bool) -> None:
        self._mock.reachable = value
