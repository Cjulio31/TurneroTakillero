from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_state import AppState
from app.controllers.config_controller import ConfigController
from app.services.autostart import AutostartError
from app.services.errors import SecretStoreError
from app.ui.status_indicator import STATUS_STYLE
from app.ui.theme import state_level
from app.ui.widgets import (
    ActionBar,
    Pill,
    Switch,
    bind_icon,
    card,
    card_header,
    connect_changes,
    field,
    header_row,
    hint,
)

SAVED_TEXT = "Configuración guardada. Se aplicará en la próxima conexión."


class ConfigurationPage(QWidget):
    """Configuración del HUB y de la terminal."""

    def __init__(
        self,
        controller: ConfigController,
        hub_status: str,
        state: AppState | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("Page")
        self._controller = controller
        self._loading = False

        self.hub_url = QLineEdit()
        self.hub_url.setPlaceholderText("https://hub.midominio.com")
        self.terminal_id = QLineEdit()
        self.terminal_id.setPlaceholderText("TERM-001")
        self.terminal_name = QLineEdit()
        self.terminal_location = QLineEdit()
        self.terminal_location.setPlaceholderText("Ej.: Piso 2, ventanilla 3")
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self._reveal = QPushButton("Mostrar")
        self._reveal.setCheckable(True)
        self._reveal.toggled.connect(self._toggle_token)
        bind_icon(self._reveal, "eye", "text2", 16)
        self.timeout = QSpinBox()
        self.timeout.setRange(1, 300)
        self.timeout.setSuffix(" s")
        self.reconnect = QSpinBox()
        self.reconnect.setRange(1, 60)
        self.reconnect.setSuffix(" s")
        self.start_with_windows = Switch("Iniciar con Windows")

        self.hub_indicator = Pill()
        self._set_hub_status(hub_status)
        if state is not None:
            state.status_changed.connect(
                lambda component, status: component == "hub" and self._set_hub_status(status)
            )

        header, _ = header_row("Configuración", "Conexión con el HUB y datos de esta terminal")

        token_row = QHBoxLayout()
        token_row.setSpacing(8)
        token_row.addWidget(self.token, 1)
        token_row.addWidget(self._reveal)
        token_field = QWidget()
        token_field.setLayout(token_row)
        token_row.setContentsMargins(0, 0, 0, 0)

        hub = card()
        hub_layout = QVBoxLayout(hub)
        hub_layout.setContentsMargins(22, 20, 22, 20)
        hub_layout.setSpacing(14)
        hub_layout.addLayout(card_header("globe", "HUB", self.hub_indicator))
        hub_layout.addWidget(field("URL del HUB", self.hub_url))
        hub_layout.addWidget(field("Token / API Key", token_field))
        timings = QHBoxLayout()
        timings.setSpacing(14)
        timings.addWidget(field("Timeout", self.timeout))
        timings.addWidget(field("Intervalo de reconexión", self.reconnect))
        hub_layout.addLayout(timings)
        hub_layout.addStretch(1)

        terminal = card()
        terminal_layout = QVBoxLayout(terminal)
        terminal_layout.setContentsMargins(22, 20, 22, 20)
        terminal_layout.setSpacing(14)
        terminal_layout.addLayout(card_header("monitor", "TERMINAL"))
        terminal_layout.addWidget(field("Terminal ID", self.terminal_id))
        terminal_layout.addWidget(field("Nombre", self.terminal_name))
        terminal_layout.addWidget(field("Ubicación", self.terminal_location))
        terminal_layout.addWidget(self.start_with_windows)
        self._autostart_hint = hint("Abre la aplicación en la bandeja al iniciar sesión.")
        terminal_layout.addWidget(self._autostart_hint)
        terminal_layout.addStretch(1)
        supported = controller.autostart_supported()
        self.start_with_windows.setVisible(supported)
        self._autostart_hint.setVisible(supported)

        cards = QHBoxLayout()
        cards.setSpacing(20)
        cards.addWidget(hub, 1)
        cards.addWidget(terminal, 1)

        self.action_bar = ActionBar("Se aplicarán en la próxima conexión con el HUB.")
        self.action_bar.save_button.clicked.connect(self.save)
        self.action_bar.discard_button.clicked.connect(self.load)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)
        layout.addLayout(header)
        layout.addLayout(cards, 1)
        layout.addWidget(self.action_bar)

        self.load()
        for widget in (
            self.hub_url,
            self.token,
            self.timeout,
            self.reconnect,
            self.terminal_id,
            self.terminal_name,
            self.terminal_location,
            self.start_with_windows,
        ):
            connect_changes(widget, self._mark_dirty)

    def _set_hub_status(self, status: str) -> None:
        text = STATUS_STYLE.get(status, STATUS_STYLE["UNKNOWN"])[0]
        self.hub_indicator.set_state(state_level(status), text)

    def _toggle_token(self, shown: bool) -> None:
        self.token.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)
        self._reveal.setText("Ocultar" if shown else "Mostrar")

    def _mark_dirty(self) -> None:
        if not self._loading:
            self.action_bar.set_dirty(True)

    def load(self) -> None:
        self._loading = True
        cfg = self._controller.load()
        self.hub_url.setText(cfg.hub_url)
        self.token.setText(cfg.api_token)
        self.timeout.setValue(cfg.hub_timeout)
        self.reconnect.setValue(cfg.reconnect_interval)
        self.terminal_id.setText(cfg.terminal_id)
        self.terminal_name.setText(cfg.terminal_name)
        self.terminal_location.setText(cfg.terminal_location)
        self.start_with_windows.setChecked(self._controller.autostart_enabled())
        self._loading = False
        self.action_bar.set_dirty(False)

    def save(self) -> bool:
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
            self.action_bar.show_result(f"No guardado: {exc}", "err")
            return False
        if self._controller.autostart_supported():
            try:
                self._controller.set_autostart(self.start_with_windows.isChecked())
            except AutostartError as exc:
                self.action_bar.show_result(
                    f"Guardado, pero no se pudo cambiar el inicio con Windows: {exc}", "err"
                )
                return False
        self.action_bar.show_result(SAVED_TEXT, "ok")
        return True
