from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.turns_controller import TurnsController
from app.ui import dialogs
from app.ui.theme import TURN_STATUS_TEXT, theme
from app.ui.widgets import (
    STATUS_ROLE,
    MessageBanner,
    PillDelegate,
    bind_icon,
    header_row,
    hint,
    retint_table,
    style_cell,
    style_table,
)
from app.utils import constants


class TurnsPage(QWidget):
    """Turnos pendientes (RECEIVED / PROCESSING / ERROR) con opción de reintento."""

    COLUMNS = ("Turno", "Message ID", "Estado", "Error")
    CELL_STYLES = {0: {"mono": 18, "bold": True}, 1: {"mono": 12, "muted": True}}

    def __init__(self, controller: TurnsController, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Page")
        self._controller = controller

        header, self._subtitle = header_row("Turnos", "Pendientes y en error")
        self.retry_button = QPushButton("REINTENTAR")
        self.retry_button.setProperty("primary", True)
        self.retry_button.setEnabled(False)  # solo con un turno en ERROR seleccionado
        self.retry_button.clicked.connect(self._retry)
        bind_icon(self.retry_button, "refresh", "on_accent")
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self.refresh)
        header.addWidget(self.retry_button)
        header.addWidget(refresh)

        self.table = QTableWidget(0, len(self.COLUMNS))
        style_table(self.table, self.COLUMNS, [90, 300, 180, None])
        self.table.setItemDelegateForColumn(2, PillDelegate(self.table))
        self.table.itemSelectionChanged.connect(self._update_retry_enabled)
        self.empty = QLabel("No hay turnos pendientes")
        self.empty.setObjectName("EmptyState")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message = MessageBanner()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty, 1)
        layout.addWidget(self.message)
        layout.addWidget(hint("Solo los turnos en ERROR se pueden reintentar."))
        theme.changed.connect(self._retint)  # método (no lambda): se desconecta al destruirse
        self.refresh()

    def _retint(self, *_: object) -> None:
        retint_table(self.table, self.CELL_STYLES)

    def refresh(self, *_: object) -> None:
        turns = self._controller.pending()
        self.table.setRowCount(len(turns))
        for row, t in enumerate(turns):
            values = (
                f"{t.turn_number:03d}",
                t.message_id,
                TURN_STATUS_TEXT.get(t.status, t.status),
                t.error_message or "",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(STATUS_ROLE, t.status)
                style_cell(item, status=t.status, **self.CELL_STYLES.get(col, {}))
                self.table.setItem(row, col, item)
        self.table.setVisible(bool(turns))
        self.empty.setVisible(not turns)
        self._subtitle.setText(f"Pendientes y en error · {len(turns)} turno(s)")
        self._update_retry_enabled()

    def _selected_error_row(self) -> int:
        """Fila seleccionada si es un turno en ERROR; -1 si no hay o no se puede reintentar."""
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0) or not self.table.item(row, 2):
            return -1
        status = self.table.item(row, 2).data(STATUS_ROLE)
        return row if status == constants.STATUS_ERROR else -1

    def _update_retry_enabled(self) -> None:
        self.retry_button.setEnabled(self._selected_error_row() >= 0)

    def _retry(self) -> None:
        row = self._selected_error_row()
        if row < 0:
            return
        turn = self.table.item(row, 0).text()
        if not dialogs.confirm(
            self,
            "Reintentar turno",
            f"¿Reintentar el turno {turn}?\n\nPuede volver a imprimir el ticket. Verifique antes "
            "que no salió impreso.",
        ):
            return
        text, level = self._controller.retry(self.table.item(row, 1).text())
        self.message.set_message(text, level)
        self.refresh()
