from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from app.controllers.dashboard_controller import DashboardController
from app.ui.status_indicator import StatusIndicator
from app.utils import constants

_STATUS_TEXT = {
    constants.STATUS_RECEIVED: "RECIBIDO",
    constants.STATUS_PROCESSING: "PROCESANDO",
    constants.STATUS_SENT: "ENVIADO",
    constants.STATUS_PRINTED: "IMPRESO",
    constants.STATUS_COMPLETED: "COMPLETADO",
    constants.STATUS_ERROR: "ERROR",
}


class DashboardPage(QWidget):
    def __init__(self, controller: DashboardController, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        state = controller.state

        title = QLabel("ÚLTIMO TURNO")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._number = QLabel("---")
        self._number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._number.setStyleSheet("font-size: 96px; font-weight: 700;")
        self._turn_status = QLabel("Sin turnos")
        self._turn_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._turn_status.setStyleSheet("font-size: 20px;")

        self._indicators = {
            "hub": StatusIndicator("HUB", state.status("hub")),
            "serial": StatusIndicator("SERIAL", state.status("serial")),
            "printer": StatusIndicator("IMPRESORA", state.status("printer")),
            "database": StatusIndicator("BASE DE DATOS", state.status("database")),
        }
        self._health = QLabel()
        self._received = QLabel()
        self._printed = QLabel()

        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        box_layout = QVBoxLayout(box)
        for indicator in self._indicators.values():
            box_layout.addWidget(indicator)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self._number)
        layout.addWidget(self._turn_status)
        layout.addSpacing(16)
        layout.addWidget(box)
        layout.addWidget(self._received)
        layout.addWidget(self._printed)
        layout.addWidget(self._health)
        layout.addStretch(1)

        state.status_changed.connect(self._on_status_changed)
        state.last_times_changed.connect(self.refresh)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(2000)
        self.refresh()

    def _on_status_changed(self, component: str, status: str) -> None:
        indicator = self._indicators.get(component)
        if indicator:
            indicator.set_status(status)

    def refresh(self) -> None:
        turn = self._controller.last_turn()
        if turn:
            self._number.setText(f"{turn.turn_number:03d}")
            self._turn_status.setText(_STATUS_TEXT.get(turn.status, turn.status))
        else:
            self._number.setText("---")
            self._turn_status.setText("Sin turnos")
        state = self._controller.state
        self._received.setText(f"Último recibido: {state.last_received or '--'}")
        self._printed.setText(f"Último impreso:  {state.last_printed or '--'}")
        report = self._controller.health_report()
        if report is not None:
            self._health.setText(f"Pendientes: {report.pending} · En error: {report.errors}")
