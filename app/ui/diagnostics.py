from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_state import ERROR, OK
from app.controllers.diagnostics_controller import DiagnosticResult, DiagnosticsController
from app.ui.status_indicator import StatusIndicator


class DiagnosticsPage(QWidget):
    def __init__(self, controller: DiagnosticsController, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        state = controller.state

        self._indicators = {
            "hub": StatusIndicator("HUB", state.status("hub")),
            "serial": StatusIndicator("SERIAL", state.status("serial")),
            "printer": StatusIndicator("IMPRESORA", state.status("printer")),
            "database": StatusIndicator("BASE DE DATOS", state.status("database")),
        }
        status_box = QGroupBox("Estado")
        status_layout = QVBoxLayout(status_box)
        for indicator in self._indicators.values():
            status_layout.addWidget(indicator)

        self.test_turn = QSpinBox()
        self.test_turn.setRange(1, 255)
        self.test_turn.setValue(25)
        actions = QGroupBox("Acciones")
        grid = QGridLayout(actions)
        buttons = (
            ("Probar HUB", lambda: self._show(controller.test_hub())),
            ("Probar Serial", lambda: self._show(controller.test_serial())),
            ("Probar impresora", lambda: self._show(controller.test_printer())),
            ("Probar base de datos", self.check_database),
            ("Ver logs", self.load_logs),
            ("Borrar logs", lambda: self.clear_logs()),
        )
        for i, (text, handler) in enumerate(buttons):
            button = QPushButton(text)
            button.clicked.connect(handler)
            grid.addWidget(button, i // 3, i % 3)
        test_row = QHBoxLayout()
        test_row.addWidget(QLabel("Turno de prueba"))
        test_row.addWidget(self.test_turn)
        send = QPushButton("Enviar turno de prueba")
        send.clicked.connect(lambda: self._show(controller.send_test_turn(self.test_turn.value())))
        test_row.addWidget(send)
        test_row.addStretch(1)
        grid.addLayout(test_row, 2, 0, 1, 3)

        self.result = QLabel()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(status_box)
        layout.addWidget(actions)
        layout.addWidget(self.result)
        layout.addWidget(self.log_view, 1)

        state.status_changed.connect(self._on_status_changed)
        self.check_database()

    def _on_status_changed(self, component: str, status: str) -> None:
        indicator = self._indicators.get(component)
        if indicator:
            indicator.set_status(status)

    def _show(self, result: DiagnosticResult) -> None:
        self.result.setText(("✔ " if result.ok else "✖ ") + result.message)

    def check_database(self) -> None:
        result = self._controller.check_database()
        self._controller.state.set_status("database", OK if result.ok else ERROR)
        self._show(result)

    def clear_logs(self, confirm: bool = True) -> None:
        if confirm:
            answer = QMessageBox.question(
                self,
                "Borrar logs",
                "Se borrará el registro de actividad (logs). Los turnos y la configuración "
                "no se tocan.\n\n¿Continuar?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._show(self._controller.clear_logs())
        self.load_logs()

    def load_logs(self) -> None:
        self.log_view.setPlainText(self._controller.read_log_tail())
