from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.controllers.dashboard_controller import DashboardController
from app.services.health_service import LEVEL_DEGRADED, LEVEL_DOWN, LEVEL_OK, HealthReport
from app.ui import icons
from app.ui.status_indicator import StatusIndicator
from app.ui.theme import LEVEL_ICON, TURN_STATUS_TEXT, blend, theme, turn_level
from app.ui.widgets import Pill, caption, header_row, mono_font

_DAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)

# nivel de salud -> (título, nivel visual)
_HEALTH = {
    LEVEL_OK: ("OPERATIVO", "ok"),
    LEVEL_DEGRADED: ("ATENCIÓN", "warn"),
    LEVEL_DOWN: ("FUERA DE SERVICIO", "err"),
}


def _clock_texts() -> tuple[str, str]:
    now = datetime.now()
    return now.strftime("%H:%M:%S"), f"{_DAYS[now.weekday()]} {now.day} de {_MONTHS[now.month - 1]}"


class _HealthBanner(QFrame):
    """Estado global de la terminal, legible de lejos: OPERATIVO / ATENCIÓN / FUERA DE SERVICIO."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("HealthBanner")
        self._level = "off"
        self._circle = QLabel()
        self._circle.setFixedSize(56, 56)
        self._circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title = QLabel()
        self._summary = QLabel()
        self.pending = QLabel("0")
        self.errors = QLabel("0")

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self._title)
        text.addWidget(self._summary)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(20)
        layout.addWidget(self._circle)
        layout.addLayout(text, 1)
        layout.addLayout(self._counter(self.pending, "PENDIENTES"))
        layout.addSpacing(12)
        layout.addLayout(self._counter(self.errors, "EN ERROR"))
        theme.changed.connect(self._refresh)
        self.set_report(None)

    @staticmethod
    def _counter(value: QLabel, label: str) -> QVBoxLayout:
        value.setProperty("mono", True)
        value.setAlignment(Qt.AlignmentFlag.AlignRight)
        caption_label = caption(label, "CardCaption")
        caption_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        column = QVBoxLayout()
        column.setSpacing(0)
        column.addWidget(value)
        column.addWidget(caption_label)
        return column

    def set_report(self, report: HealthReport | None) -> None:
        if report is None:
            self._level, self._head, self._sub = "off", "SIN MONITOREO", "Monitoreo no disponible"
            pending = errors = 0
        else:
            self._head, self._level = _HEALTH.get(report.level, ("ESTADO DESCONOCIDO", "off"))
            self._sub = report.summary
            pending, errors = report.pending, report.errors
        self.pending.setText(str(pending))
        self.errors.setText(str(errors))
        self._errors_count = errors
        self._refresh()

    def _refresh(self, *_: object) -> None:
        p = theme.palette
        fg = p.fg(self._level)
        self.setStyleSheet(
            f"QFrame#HealthBanner {{ background: {p.bg_of(self._level)}; "
            f"border: 1px solid {p.border_of(self._level)}; border-radius: 18px; }}"
        )
        self._circle.setStyleSheet(
            f"background: {blend(fg, p.bg_of(self._level), 0.2)}; border-radius: 28px;"
        )
        self._circle.setPixmap(icons.pixmap(LEVEL_ICON[self._level], fg, 30, 2.2))
        self._title.setText(self._head)
        self._title.setStyleSheet(
            f"font-size: 30px; font-weight: 800; color: {fg}; background: transparent;"
        )
        self._summary.setText(self._sub)
        self._summary.setStyleSheet(f"font-size: 15px; color: {p.text2}; background: transparent;")
        number = "font-size: 30px; font-weight: 700; background: transparent;"
        self.pending.setStyleSheet(number + f"color: {p.text};")
        errors_color = p.err if getattr(self, "_errors_count", 0) else p.text
        self.errors.setStyleSheet(number + f"color: {errors_color};")


class _TurnCard(QFrame):
    """Último turno: el número se agranda con la tarjeta (se lee de lejos)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.number = QLabel("---")
        self.number.setProperty("mono", True)
        self.status = Pill("Sin turnos", "off")
        self.times = QLabel()
        self.times.setObjectName("Hint")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)
        layout.addWidget(caption("ÚLTIMO TURNO", "CardCaption"))
        layout.addStretch(1)
        layout.addWidget(self.number)
        layout.addStretch(1)
        layout.addWidget(self.status)
        layout.addWidget(self.times)
        self._fit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        size = max(56, min(168, int(self.height() * 0.40), int((self.width() - 56) / 1.9)))
        self.number.setStyleSheet(
            f"font-size: {size}px; font-weight: 700; background: transparent;"
        )
        self.number.setFont(mono_font(size, True))


class DashboardPage(QWidget):
    def __init__(self, controller: DashboardController, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")
        self._controller = controller
        state = controller.state

        header, self._subtitle = header_row("Inicio", controller.terminal_label())
        self._clock = QLabel()
        self._clock.setProperty("mono", True)
        self._date = QLabel()
        self._date.setObjectName("PageSubtitle")
        self._date.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._clock.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        clock_box.addWidget(self._clock)
        clock_box.addWidget(self._date)
        header.addLayout(clock_box)

        self._banner = _HealthBanner()
        self._turn_card = _TurnCard()
        self._number = self._turn_card.number
        self._turn_status = self._turn_card.status

        self._indicators = {
            "hub": StatusIndicator("HUB", state.status("hub"), "globe"),
            "serial": StatusIndicator("SERIAL", state.status("serial"), "plug"),
            "printer": StatusIndicator("IMPRESORA", state.status("printer"), "printer"),
            "database": StatusIndicator("BASE DE DATOS", state.status("database"), "database"),
        }
        grid = QGridLayout()
        grid.setSpacing(16)
        for i, indicator in enumerate(self._indicators.values()):
            grid.addWidget(indicator, i // 2, i % 2)
            grid.setRowStretch(i // 2, 1)
            grid.setColumnStretch(i % 2, 1)

        body = QHBoxLayout()
        body.setSpacing(20)
        body.addWidget(self._turn_card, 1)
        body.addLayout(grid, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)
        layout.addLayout(header)
        layout.addWidget(self._banner)
        layout.addLayout(body, 1)

        state.status_changed.connect(self._on_status_changed)
        state.last_times_changed.connect(self.refresh)
        controller.on_health_changed(self._banner.set_report)
        # Los temporizadores solo corren mientras la pantalla se ve (showEvent/hideEvent): oculta
        # en otra página o en la bandeja no consulta la base de datos ni actualiza el reloj.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick)
        self._tick()
        self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._tick()
        self.refresh()
        self._timer.start(2000)
        self._clock_timer.start(1000)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()
        self._clock_timer.stop()

    def _tick(self) -> None:
        clock, date = _clock_texts()
        self._clock.setText(clock)
        self._clock.setStyleSheet("font-size: 22px; font-weight: 500; background: transparent;")
        self._date.setText(date)

    def _on_status_changed(self, component: str, status: str) -> None:
        indicator = self._indicators.get(component)
        if indicator:
            indicator.set_status(status)

    def refresh(self) -> None:
        turn = self._controller.last_turn()
        if turn:
            self._number.setText(f"{turn.turn_number:03d}")
            self._turn_status.set_state(
                turn_level(turn.status), TURN_STATUS_TEXT.get(turn.status, turn.status)
            )
        else:
            self._number.setText("---")
            self._turn_status.set_state("off", "Sin turnos")
        state = self._controller.state
        self._turn_card.times.setText(
            f"Recibido {state.last_received or '--'} · Impreso {state.last_printed or '--'}"
        )
        self._subtitle.setText(self._controller.terminal_label())
        for component, detail in self._controller.details().items():
            self._indicators[component].set_detail(detail)
        self._banner.set_report(self._controller.health_report())
