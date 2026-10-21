from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.history_controller import HistoryController
from app.ui.theme import TURN_STATUS_TEXT, theme
from app.ui.widgets import (
    STATUS_ROLE,
    PillDelegate,
    Switch,
    bind_icon,
    card,
    field,
    header_row,
    retint_table,
    style_cell,
    style_table,
)


class HistoryPage(QWidget):
    COLUMNS = ("Fecha", "Hora", "Turno", "Message ID", "Estado", "Terminal", "Error")
    CELL_STYLES = {
        0: {"mono": 12, "muted": True},
        1: {"mono": 12, "muted": True},
        2: {"mono": 16, "bold": True},
        3: {"mono": 12, "muted": True},
    }

    def __init__(self, controller: HistoryController, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")
        self._controller = controller

        header, self._subtitle = header_row(
            "Historial", "Todos los turnos recibidos por esta terminal"
        )
        self._count = QLabel()
        self._count.setObjectName("PageSubtitle")
        header.addWidget(self._count, 0, Qt.AlignmentFlag.AlignBottom)

        self.use_date = Switch("Fecha")
        self.use_date.toggled.connect(lambda on: self.date.setEnabled(on))
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        self.date.setEnabled(False)  # solo filtra si el interruptor está activo
        self.turn = QSpinBox()
        self.turn.setRange(0, 255)
        self.turn.setSpecialValueText("Todos")
        self.status = QComboBox()
        self.status.addItem("Todos", "")
        for s in controller.statuses:
            self.status.addItem(TURN_STATUS_TEXT.get(s, s), s)
        search = QPushButton("Buscar")
        search.setProperty("primary", True)
        search.clicked.connect(self.refresh)
        bind_icon(search, "search", "on_accent", 16)
        clear = QPushButton("Limpiar")
        clear.clicked.connect(self.clear_filters)

        date_box = QVBoxLayout()
        date_box.setSpacing(6)
        date_box.addWidget(self.use_date)
        date_box.addWidget(self.date)
        filters_card = card()
        filters = QHBoxLayout(filters_card)
        filters.setContentsMargins(18, 14, 18, 14)
        filters.setSpacing(14)
        filters.addLayout(date_box)
        filters.addWidget(field("Turno", self.turn))
        filters.addWidget(field("Estado", self.status))
        filters.addStretch(1)
        filters.addWidget(clear, 0, Qt.AlignmentFlag.AlignBottom)
        filters.addWidget(search, 0, Qt.AlignmentFlag.AlignBottom)

        self.table = QTableWidget(0, len(self.COLUMNS))
        style_table(self.table, self.COLUMNS, [112, 84, 62, 170, 146, 90, None])
        self.table.setItemDelegateForColumn(4, PillDelegate(self.table))
        self.empty = QLabel("Sin resultados para el filtro")
        self.empty.setObjectName("EmptyState")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addWidget(filters_card)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty, 1)
        theme.changed.connect(self._retint)  # método (no lambda): se desconecta al destruirse
        self.refresh()

    def _retint(self, *_: object) -> None:
        retint_table(self.table, self.CELL_STYLES)

    def clear_filters(self) -> None:
        self.use_date.setChecked(False)
        self.date.setDate(QDate.currentDate())
        self.turn.setValue(0)
        self.status.setCurrentIndex(0)
        self.refresh()

    def refresh(self, *_: object) -> None:
        turns = self._controller.search(
            date=self.date.date().toString("yyyy-MM-dd") if self.use_date.isChecked() else None,
            turn_number=self.turn.value() or None,
            status=self.status.currentData(),
        )
        self.table.setRowCount(len(turns))
        for row, t in enumerate(turns):
            day, _, time = t.received_at.partition("T")
            values = (
                day,
                time,
                f"{t.turn_number:03d}",
                t.message_id,
                TURN_STATUS_TEXT.get(t.status, t.status),
                t.terminal_id,
                t.error_message or "",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(STATUS_ROLE, t.status)
                style_cell(item, status=t.status, **self.CELL_STYLES.get(col, {}))
                self.table.setItem(row, col, item)
        self.table.setVisible(bool(turns))
        self.empty.setVisible(not turns)
        self._count.setText(f"{len(turns)} resultado(s)")
