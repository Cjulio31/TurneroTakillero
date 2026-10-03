from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from app.context import AppContext
from app.controllers.config_controller import ConfigController
from app.controllers.dashboard_controller import DashboardController
from app.controllers.diagnostics_controller import DiagnosticsController
from app.controllers.history_controller import HistoryController
from app.controllers.turns_controller import TurnsController
from app.ui.about import AboutPage
from app.ui.configuration import ConfigurationPage
from app.ui.dashboard import DashboardPage
from app.ui.diagnostics import DiagnosticsPage
from app.ui.hardware import HardwarePage
from app.ui.history import HistoryPage
from app.ui.status_indicator import STATUS_STYLE
from app.ui.tray import TrayController
from app.ui.turns import TurnsPage
from app.utils import constants

PAGES = ("Inicio", "Turnos", "Historial", "Configuración", "Hardware", "Diagnóstico", "Acerca de")


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(constants.APP_NAME)
        self.resize(960, 640)
        self._quitting = False

        config = ConfigController(ctx.config_service)
        self.pages: dict[str, QWidget] = {
            "Inicio": DashboardPage(DashboardController(ctx.state, ctx.turns)),
            "Turnos": TurnsPage(TurnsController(ctx.turns)),
            "Historial": HistoryPage(HistoryController(ctx.turns)),
            "Configuración": ConfigurationPage(config, ctx.state.status("hub")),
            "Hardware": HardwarePage(config),
            "Diagnóstico": DiagnosticsPage(DiagnosticsController(ctx.state, ctx.db)),
            "Acerca de": AboutPage(),
        }
        self.menu = QListWidget()
        self.menu.setFixedWidth(170)
        self.menu.setStyleSheet("QListWidget::item { padding: 10px; font-size: 14px; }")
        self.stack = QStackedWidget()
        for name in PAGES:
            self.menu.addItem(name)
            self.stack.addWidget(self.pages[name])
        self.menu.currentRowChanged.connect(self._on_page_changed)
        self.menu.setCurrentRow(0)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.menu)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.tray = TrayController(self)
        self.tray.open_requested.connect(self.show_window)
        self.tray.configuration_requested.connect(lambda: self.show_window("Configuración"))
        self.tray.quit_requested.connect(self.quit)
        ctx.state.status_changed.connect(self._update_tray_status)

    def _on_page_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _update_tray_status(self, *_: object) -> None:
        text, color = STATUS_STYLE[self.ctx.state.status("hub")]
        self.tray.set_status_text(f"HUB {text.lower()}", color)

    def show_window(self, page: str | None = None) -> None:
        if page in PAGES:
            self.menu.setCurrentRow(PAGES.index(page))
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
