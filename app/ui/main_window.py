from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from app.communication.mock_hub_client import MockHubClient
from app.context import AppContext
from app.controllers.config_controller import ConfigController
from app.controllers.dashboard_controller import DashboardController
from app.controllers.diagnostics_controller import DiagnosticsController
from app.controllers.history_controller import HistoryController
from app.controllers.turns_controller import TurnsController
from app.services.health_service import LEVEL_DEGRADED, LEVEL_DOWN, HealthReport, HealthService
from app.services.hub_service import HubService
from app.services.printer_service import PrinterService
from app.services.serial_service import SerialService
from app.services.turn_service import TurnService
from app.ui.about import AboutPage
from app.ui.configuration import ConfigurationPage
from app.ui.dashboard import DashboardPage
from app.ui.diagnostics import DiagnosticsPage
from app.ui.hardware import HardwarePage
from app.ui.history import HistoryPage
from app.ui.mock_hub import MockHubPage
from app.ui.status_indicator import STATUS_STYLE
from app.ui.tray import TrayController
from app.ui.turns import TurnsPage
from app.utils import constants

PAGES = ("Inicio", "Turnos", "Historial", "Configuración", "Hardware", "Diagnóstico", "Acerca de")


class MainWindow(QMainWindow):
    def __init__(
        self,
        ctx: AppContext,
        hub: HubService | None = None,
        turn_service: TurnService | None = None,
        serial: SerialService | None = None,
        printer: PrinterService | None = None,
        health: HealthService | None = None,
    ):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(constants.APP_NAME)
        self.resize(960, 640)
        self._quitting = False

        config = ConfigController(ctx.config_service)
        self.pages: dict[str, QWidget] = {
            "Inicio": DashboardPage(DashboardController(ctx.state, ctx.turns, health)),
            "Turnos": TurnsPage(TurnsController(ctx.turns, turn_service)),
            "Historial": HistoryPage(HistoryController(ctx.turns)),
            "Configuración": ConfigurationPage(config, ctx.state.status("hub")),
            "Hardware": HardwarePage(config),
            "Diagnóstico": DiagnosticsPage(
                DiagnosticsController(ctx.state, ctx.db, serial, printer, hub)
            ),
            "Acerca de": AboutPage(),
        }
        names = list(PAGES)
        if hub is not None and isinstance(hub.client, MockHubClient):
            self.pages["Mock HUB"] = MockHubPage(hub.client)
            names.append("Mock HUB")
        self.menu = QListWidget()
        self.menu.setFixedWidth(170)
        self.menu.setStyleSheet("QListWidget::item { padding: 10px; font-size: 14px; }")
        self.stack = QStackedWidget()
        for name in names:
            self.menu.addItem(name)
            self.stack.addWidget(self.pages[name])
        self.menu.currentRowChanged.connect(self._on_page_changed)
        self.menu.setCurrentRow(0)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.menu)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        if turn_service is not None:
            turn_service.turn_changed.connect(lambda _id: self._refresh_turn_pages())

        self.tray = TrayController(self)
        self.tray.open_requested.connect(self.show_window)
        self.tray.configuration_requested.connect(lambda: self.show_window("Configuración"))
        self.tray.quit_requested.connect(self.quit)
        if health is not None:
            health.report_changed.connect(self._update_tray_health)
        else:
            ctx.state.status_changed.connect(self._update_tray_status)

    def _on_page_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _refresh_turn_pages(self) -> None:
        for name in ("Inicio", "Turnos"):
            self.pages[name].refresh()

    def _update_tray_status(self, *_: object) -> None:
        text, color = STATUS_STYLE[self.ctx.state.status("hub")]
        self.tray.set_status_text(f"HUB {text.lower()}", color)

    def _update_tray_health(self, report: HealthReport) -> None:
        color = {LEVEL_DOWN: "#c0392b", LEVEL_DEGRADED: "#d99a00"}.get(report.level, "#2e9e45")
        self.tray.set_status_text(report.summary, color)

    def show_window(self, page: str | None = None) -> None:
        for row in range(self.menu.count()):
            if self.menu.item(row).text() == page:
                self.menu.setCurrentRow(row)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit(self) -> None:
        self._quitting = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        # Con bandeja disponible, cerrar la ventana solo la oculta: se sigue escuchando al HUB.
        if self.tray.available and not self._quitting:
            self.hide()
            event.ignore()
            return
        self.tray.icon.hide()
        event.accept()
        QApplication.quit()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type().name == "WindowStateChange" and self.isMinimized() and self.tray.available:
            self.hide()
