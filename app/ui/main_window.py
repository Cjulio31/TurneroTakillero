import logging
import sqlite3

import shiboken6
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.communication.mock_hub_client import MockHubClient
from app.context import AppContext
from app.controllers.config_controller import ConfigController
from app.controllers.dashboard_controller import DashboardController
from app.controllers.diagnostics_controller import DiagnosticsController
from app.controllers.history_controller import HistoryController
from app.controllers.turns_controller import TurnsController
from app.models.configuration import Configuration
from app.services.autostart import AutostartStore
from app.services.errors import SecretStoreError
from app.services.health_service import LEVEL_DEGRADED, LEVEL_DOWN, HealthReport, HealthService
from app.services.hub_service import HubService
from app.services.printer_service import PrinterService
from app.services.serial_service import SerialService
from app.services.turn_service import TurnService
from app.ui import icons
from app.ui.about import AboutPage
from app.ui.configuration import ConfigurationPage
from app.ui.dashboard import DashboardPage
from app.ui.diagnostics import DiagnosticsPage
from app.ui.hardware import HardwarePage
from app.ui.history import HistoryPage
from app.ui.icons import app_icon
from app.ui.mock_hub import MockHubPage
from app.ui.status_indicator import STATUS_STYLE
from app.ui.theme import DARK, LIGHT, theme
from app.ui.tray import TrayController
from app.ui.turns import TurnsPage
from app.ui.widgets import BADGE_ROLE, NavDelegate
from app.utils import constants

log = logging.getLogger(__name__)

PAGES = ("Inicio", "Turnos", "Historial", "Configuración", "Hardware", "Diagnóstico", "Acerca de")
NAV_ICONS = {
    "Inicio": "home",
    "Turnos": "list",
    "Historial": "clock",
    "Configuración": "sliders",
    "Hardware": "chip",
    "Diagnóstico": "activity",
    "Acerca de": "info",
    "Mock HUB": "zap",
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        ctx: AppContext,
        hub: HubService | None = None,
        turn_service: TurnService | None = None,
        serial: SerialService | None = None,
        printer: PrinterService | None = None,
        health: HealthService | None = None,
        autostart: AutostartStore | None = None,
    ):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(constants.APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1100, 700)
        self.setMinimumSize(900, 600)
        self._quitting = False

        self._config = ConfigController(ctx.config_service, autostart)
        self.pages: dict[str, QWidget] = {
            "Inicio": DashboardPage(
                DashboardController(ctx.state, ctx.turns, health, ctx.config_service.load)
            ),
            "Turnos": TurnsPage(TurnsController(ctx.turns, turn_service)),
            "Historial": HistoryPage(HistoryController(ctx.turns)),
            "Configuración": ConfigurationPage(self._config, ctx.state.status("hub"), ctx.state),
            "Hardware": HardwarePage(self._config, ctx.state),
            "Diagnóstico": DiagnosticsPage(
                DiagnosticsController(ctx.state, ctx.db, serial, printer)
            ),
            "Acerca de": AboutPage(),
        }
        names = list(PAGES)
        if hub is not None and isinstance(hub.client, MockHubClient):
            self.pages["Mock HUB"] = MockHubPage(hub.client)
            names.append("Mock HUB")
        self._names = names

        self.menu = QListWidget()
        self.menu.setObjectName("Nav")
        self.menu.setIconSize(QSize(20, 20))
        self.menu.setItemDelegate(NavDelegate(self.menu))
        self.menu.setFrameShape(QFrame.Shape.NoFrame)
        self.menu.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        for name in names:
            self.menu.addItem(QListWidgetItem(name))
            self.stack.addWidget(self._scrollable(self.pages[name]))
        self.menu.currentRowChanged.connect(self._on_page_changed)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self._apply_theme_assets()
        self.menu.setCurrentRow(0)

        theme.changed.connect(self._apply_theme_assets)
        ctx.config_service.add_listener(self._on_config_saved)
        if turn_service is not None:
            turn_service.turn_changed.connect(lambda _id: self._refresh_turn_pages())

        self.tray = TrayController(self)
        self.tray.open_requested.connect(self.show_window)
        self.tray.configuration_requested.connect(lambda: self.show_window("Configuración"))
        self.tray.quit_requested.connect(self.quit)
        if health is not None:
            health.report_changed.connect(self._update_tray_health)
            health.report_changed.connect(lambda _report: self._update_badge())
        else:
            ctx.state.status_changed.connect(self._update_tray_status)

    # --- construcción -----------------------------------------------------------------------
    @staticmethod
    def _scrollable(page: QWidget) -> QScrollArea:
        """Cada página en un área con scroll: en ventanas chicas se desplaza, no se recorta."""
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)

        self._brand_mark = QLabel()
        self._brand_mark.setObjectName("BrandMark")
        self._brand_mark.setFixedSize(40, 40)
        self._brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Turnos")
        title.setObjectName("BrandTitle")
        self._brand_sub = QLabel()
        self._brand_sub.setObjectName("BrandSub")
        self._set_brand(self.ctx.config_service.load())
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_text.addWidget(title)
        brand_text.addWidget(self._brand_sub)
        brand = QHBoxLayout()
        brand.setContentsMargins(8, 0, 8, 14)
        brand.setSpacing(12)
        brand.addWidget(self._brand_mark)
        brand.addLayout(brand_text)
        brand.addStretch(1)

        version = QLabel(f"v{constants.APP_VERSION}")
        version.setObjectName("SidebarVersion")
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("ThemeToggle")
        self.theme_button.clicked.connect(self.toggle_theme)
        footer = QHBoxLayout()
        footer.setContentsMargins(8, 8, 0, 0)
        footer.addWidget(version)
        footer.addStretch(1)
        footer.addWidget(self.theme_button)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 16)
        layout.setSpacing(0)
        layout.addLayout(brand)
        layout.addWidget(self.menu, 1)
        layout.addLayout(footer)
        return sidebar

    # --- tema -------------------------------------------------------------------------------
    def _apply_theme_assets(self, *_: object) -> None:
        """Íconos que se dibujan por código: se recolorean al cambiar de tema."""
        p = theme.palette
        for row, name in enumerate(self._names):
            self.menu.item(row).setIcon(icons.icon(NAV_ICONS[name], p.text2, p.accent))
        self._brand_mark.setPixmap(icons.pixmap("ticket", p.accent, 22, 1.8))
        light = theme.mode == LIGHT
        self.theme_button.setText("Modo oscuro" if light else "Modo claro")
        self.theme_button.setIcon(icons.icon("moon" if light else "sun", p.muted, size=16))
        self.theme_button.setIconSize(QSize(16, 16))
        self.menu.viewport().update()

    def toggle_theme(self) -> None:
        """Alterna claro/oscuro y recuerda la elección."""
        new = DARK if theme.mode == LIGHT else LIGHT
        theme.set_mode(new)
        try:
            self._config.update(theme=new)
        except (ValueError, SecretStoreError) as exc:
            log.error("No se pudo guardar el tema: %s", exc)

    # --- marca y contadores -----------------------------------------------------------------
    def _set_brand(self, cfg: Configuration) -> None:
        self._brand_sub.setText(cfg.terminal_id or "Sin configurar")

    def _on_config_saved(self, cfg: Configuration) -> None:
        if shiboken6.isValid(self):
            self._set_brand(cfg)

    def _update_badge(self) -> None:
        """Insignia del menú 'Turnos': cantidad de turnos en ERROR que piden atención."""
        try:
            errors = self.ctx.turns.count_by_status().get(constants.STATUS_ERROR, 0)
        except sqlite3.Error:
            log.exception("No se pudo contar los turnos en error")
            errors = 0
        row = self._names.index("Turnos")
        self.menu.item(row).setData(BADGE_ROLE, errors)
        self.menu.viewport().update()

    # --- navegación -------------------------------------------------------------------------
    def _on_page_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        page = self.pages[self._names[row]]
        if hasattr(page, "refresh"):
            page.refresh()
        self._update_badge()

    def _refresh_turn_pages(self) -> None:
        for name in ("Inicio", "Turnos"):
            self.pages[name].refresh()
        self._update_badge()

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
