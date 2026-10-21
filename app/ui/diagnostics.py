from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_state import ERROR, OK
from app.controllers.diagnostics_controller import DiagnosticResult, DiagnosticsController
from app.ui import dialogs
from app.ui.status_indicator import StatusIndicator
from app.ui.widgets import MessageBanner, bind_icon, card, header_row, hint


class DiagnosticsPage(QWidget):
    def __init__(self, controller: DiagnosticsController, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")
        self._controller = controller
        state = controller.state

        self._indicators = {
            "hub": StatusIndicator("HUB", state.status("hub"), "globe", compact=True),
            "serial": StatusIndicator("SERIAL", state.status("serial"), "plug", compact=True),
            "printer": StatusIndicator(
                "IMPRESORA", state.status("printer"), "printer", compact=True
            ),
            "database": StatusIndicator(
                "BASE DE DATOS", state.status("database"), "database", compact=True
            ),
        }
        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        for indicator in self._indicators.values():
            status_row.addWidget(indicator, 1)

        buttons = (
            ("Probar HUB", "globe", False, lambda: self._show(controller.test_hub())),
            ("Probar serial", "plug", False, lambda: self._show(controller.test_serial())),
            ("Probar impresora", "printer", False, lambda: self._show(controller.test_printer())),
            ("Probar base de datos", "database", False, self.check_database),
            ("Ver logs", "file", False, self.load_logs),
            ("Borrar logs", "trash", True, lambda: self.clear_logs()),
        )
        actions = QGridLayout()
        actions.setSpacing(10)
        for i, (text, icon_name, danger, handler) in enumerate(buttons):
            button = QPushButton(text)
            button.setProperty("tool", True)
            if danger:
                button.setProperty("danger", True)
            button.clicked.connect(handler)
            bind_icon(button, icon_name, "err" if danger else "text2")
            actions.addWidget(button, i // 3, i % 3)

        self.test_turn = QSpinBox()
        self.test_turn.setRange(1, 255)
        self.test_turn.setValue(25)
        send = QPushButton("Enviar turno de prueba")
        send.setProperty("primary", True)
        send.clicked.connect(lambda: self.send_test_turn())
        bind_icon(send, "send", "on_accent", 16)
        test_card = card()
        test_row = QHBoxLayout(test_card)
        test_row.setContentsMargins(16, 10, 16, 10)
        test_row.setSpacing(12)
        test_label = QLabel("TURNO DE PRUEBA")
        test_label.setObjectName("CardCaption")
        test_row.addWidget(test_label)
        test_row.addWidget(self.test_turn)
        test_row.addWidget(send)
        test_row.addStretch(1)
        test_row.addWidget(hint("Envía bytes reales al serial. No crea turnos ni imprime."))

        self.result = MessageBanner()
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)

        header, _ = header_row("Diagnóstico", "Pruebas manuales de cada componente")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addLayout(status_row)
        layout.addLayout(actions)
        layout.addWidget(test_card)
        layout.addWidget(self.result)
        layout.addWidget(self.log_view, 1)

        state.status_changed.connect(self._on_status_changed)
        self.check_database()

    def _on_status_changed(self, component: str, status: str) -> None:
        indicator = self._indicators.get(component)
        if indicator:
            indicator.set_status(status)

    def _show(self, result: DiagnosticResult) -> None:
        self.result.set_message(result.message, "ok" if result.ok else "err")

    def check_database(self) -> None:
        result = self._controller.check_database()
        self._controller.state.set_status("database", OK if result.ok else ERROR)
        self._show(result)

    def send_test_turn(self, confirm: bool = True) -> None:
        turn = self.test_turn.value()
        if confirm and not dialogs.confirm(
            self,
            "Enviar turno de prueba",
            f"Se enviarán bytes reales al dispositivo serial: el display mostrará el turno "
            f"{turn}. No se crea ningún turno ni se imprime.\n\n¿Continuar?",
        ):
            return
        self._show(self._controller.send_test_turn(turn))

    def clear_logs(self, confirm: bool = True) -> None:
        if confirm and not dialogs.confirm(
            self,
            "Borrar logs",
            "Se borrará el registro de actividad (logs). Los turnos y la configuración "
            "no se tocan.\n\n¿Continuar?",
        ):
            return
        self._show(self._controller.clear_logs())
        self.load_logs()

    def refresh(self) -> None:
        """Al abrir la pantalla se muestra el final del log (no hace falta pulsar 'Ver logs')."""
        self.load_logs()

    def load_logs(self) -> None:
        self.log_view.setPlainText(self._controller.read_log_tail())
