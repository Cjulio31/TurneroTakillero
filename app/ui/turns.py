from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.turns_controller import TurnsController


class TurnsPage(QWidget):
    """Turnos pendientes (RECEIVED / PROCESSING / ERROR) con opción de reintento."""

    COLUMNS = ("Turno", "Message ID", "Estado", "Error")

    def __init__(self, controller: TurnsController, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.retry_button = QPushButton("REINTENTAR")
        self.retry_button.clicked.connect(self._retry)
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self.refresh)

        buttons = QHBoxLayout()
        buttons.addWidget(self.retry_button)
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        turns = self._controller.pending()
        self.table.setRowCount(len(turns))
        for row, t in enumerate(turns):
            values = (f"{t.turn_number:03d}", t.message_id, t.status, t.error_message or "")
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _retry(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self._controller.retry(self.table.item(row, 1).text())
        self.refresh()
