from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
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


class HistoryPage(QWidget):
    COLUMNS = ("Fecha", "Hora", "Turno", "Message ID", "Estado", "Origen", "Error")

    def __init__(self, controller: HistoryController, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller

        self.use_date = QCheckBox("Fecha")
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.turn = QSpinBox()
        self.turn.setRange(0, 255)
        self.turn.setSpecialValueText("Todos")
        self.status = QComboBox()
        self.status.addItem("Todos", "")
        for s in controller.statuses:
            self.status.addItem(s, s)
        search = QPushButton("Buscar")
        search.clicked.connect(self.refresh)

        filters = QHBoxLayout()
        filters.addWidget(self.use_date)
        filters.addWidget(self.date)
        filters.addWidget(QLabel("Turno"))
        filters.addWidget(self.turn)
        filters.addWidget(QLabel("Estado"))
        filters.addWidget(self.status)
        filters.addWidget(search)
        filters.addStretch(1)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
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
                t.status,
                t.terminal_id,
                t.error_message or "",
            )
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
