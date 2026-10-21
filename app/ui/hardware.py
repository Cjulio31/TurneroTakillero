from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_state import AppState
from app.controllers.config_controller import ConfigController
from app.ui.status_indicator import STATUS_STYLE
from app.ui.theme import state_level
from app.ui.widgets import (
    ActionBar,
    Pill,
    Switch,
    bind_icon,
    caption,
    card,
    card_header,
    connect_changes,
    field,
    header_row,
    hint,
)

PARITIES = (("Ninguna", "N"), ("Par", "E"), ("Impar", "O"))
# (texto visible, valor guardado): el valor lo interpreta `create_backend`, no se traduce.
PRINTER_TYPES = (
    ("(sin definir)", ""),
    ("USB", "USB"),
    ("Serial", "Serial"),
    ("Impresora de Windows", "Windows Printer"),
    ("Impresora de red", "Network Printer"),
)


class HardwarePage(QWidget):
    """Configuración del puerto serial y de la impresora."""

    def __init__(
        self,
        controller: ConfigController,
        state: AppState | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("Page")
        self._controller = controller
        self._state = state
        self._loading = False

        self.port = QComboBox()
        self.port.setEditable(True)
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self.refresh_ports)
        bind_icon(refresh, "refresh", "text", 16)
        self.baudrate = QComboBox()
        for b in (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200):
            self.baudrate.addItem(str(b), b)
        self.data_bits = QComboBox()
        for d in (5, 6, 7, 8):
            self.data_bits.addItem(str(d), d)
        self.parity = QComboBox()
        for label, value in PARITIES:
            self.parity.addItem(label, value)
        self.stop_bits = QComboBox()
        for s in (1, 2):
            self.stop_bits.addItem(str(s), s)
        self.transmissions = QSpinBox()
        self.transmissions.setRange(1, 5)
        self.header_1 = QSpinBox()
        self.header_1.setRange(0, 255)
        self.header_2 = QSpinBox()
        self.header_2.setRange(0, 255)
        self.packet_preview = QLabel()
        self.packet_preview.setProperty("mono", True)
        for header in (self.header_1, self.header_2):
            header.setToolTip("Valor decimal (0-255). Ej.: 153 = 0x99, 85 = 0x55")
            header.valueChanged.connect(self._update_preview)

        self.serial_pill = Pill()
        self.printer_pill = Pill()
        self._sync_pills()
        if state is not None:
            state.status_changed.connect(lambda *_: self._sync_pills())

        header_layout, _ = header_row(
            "Hardware", "Puerto serial del display e impresora de tiquetes"
        )

        serial_box = card()
        serial = QVBoxLayout(serial_box)
        serial.setContentsMargins(22, 20, 22, 20)
        serial.setSpacing(12)
        serial.addLayout(card_header("plug", "SERIAL", self.serial_pill))
        port_row = QHBoxLayout()
        port_row.setSpacing(10)
        port_row.addWidget(field("Puerto", self.port), 1)
        port_row.addWidget(refresh, 0, Qt.AlignmentFlag.AlignBottom)
        serial.addLayout(port_row)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.addWidget(field("Velocidad (baudios)", self.baudrate), 0, 0)
        grid.addWidget(field("Bits de datos", self.data_bits), 0, 1)
        grid.addWidget(field("Paridad", self.parity), 1, 0)
        grid.addWidget(field("Bits de parada", self.stop_bits), 1, 1)
        serial.addLayout(grid)
        protocol = QHBoxLayout()
        protocol.setSpacing(12)
        protocol.addWidget(field("Envíos por turno", self.transmissions))
        protocol.addWidget(field("Cabecera: byte 1", self.header_1))
        protocol.addWidget(field("Cabecera: byte 2", self.header_2))
        serial.addLayout(protocol)
        preview = card("Dashed")
        preview_row = QHBoxLayout(preview)
        preview_row.setContentsMargins(14, 10, 14, 10)
        preview_row.addWidget(caption("Paquete que se envía"))
        preview_row.addStretch(1)
        preview_row.addWidget(self.packet_preview)
        serial.addWidget(preview)

        self.printer_type = QComboBox()
        for label, value in PRINTER_TYPES:
            self.printer_type.addItem(label, value)
        self.printer_port = QLineEdit()
        self.printer_port.setPlaceholderText("(impresora predeterminada)")
        self.print_tickets = Switch("Imprimir tiquete al recibir un turno")
        self.print_tickets.setToolTip(
            "Desmarcado: el turno se envía al serial y se completa, pero no se imprime tiquete."
        )

        printer_box = card()
        printer = QVBoxLayout(printer_box)
        printer.setContentsMargins(22, 20, 22, 20)
        printer.setSpacing(12)
        printer.addLayout(card_header("printer", "IMPRESORA", self.printer_pill))
        highlight = card("Highlight")
        highlight_layout = QVBoxLayout(highlight)
        highlight_layout.setContentsMargins(16, 14, 16, 14)
        highlight_layout.setSpacing(4)
        highlight_layout.addWidget(self.print_tickets)
        highlight_layout.addWidget(
            hint("Apagado: el turno se envía al serial y se completa, sin imprimir.")
        )
        printer.addWidget(highlight)
        printer.addWidget(field("Método", self.printer_type))
        printer.addWidget(field("Nombre de la impresora / puerto / dirección", self.printer_port))
        printer.addStretch(1)

        columns = QHBoxLayout()
        columns.setSpacing(20)
        columns.addWidget(serial_box, 5)
        columns.addWidget(printer_box, 4)

        self.action_bar = ActionBar("Se aplicarán al guardar.")
        self.action_bar.save_button.clicked.connect(self.save)
        self.action_bar.discard_button.clicked.connect(self.load)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)
        layout.addLayout(header_layout)
        layout.addLayout(columns, 1)
        layout.addWidget(self.action_bar)

        self.refresh_ports()
        self.load()
        for widget in (
            self.port,
            self.baudrate,
            self.data_bits,
            self.parity,
            self.stop_bits,
            self.transmissions,
            self.header_1,
            self.header_2,
            self.printer_type,
            self.printer_port,
            self.print_tickets,
        ):
            connect_changes(widget, self._mark_dirty)

    def _sync_pills(self) -> None:
        for pill, component in ((self.serial_pill, "serial"), (self.printer_pill, "printer")):
            status = self._state.status(component) if self._state is not None else "UNKNOWN"
            pill.set_state(
                state_level(status), STATUS_STYLE.get(status, STATUS_STYLE["UNKNOWN"])[0]
            )

    def _update_preview(self) -> None:
        self.packet_preview.setText(
            f"{self.header_1.value():02X} {self.header_2.value():02X} <turno>"
        )

    def _mark_dirty(self) -> None:
        if not self._loading:
            self.action_bar.set_dirty(True)

    def refresh_ports(self) -> None:
        was_loading, self._loading = self._loading, True  # refrescar la lista no es un cambio
        current = self.port.currentText()
        self.port.clear()
        self.port.addItems(self._controller.available_serial_ports())
        self.port.setCurrentText(current)
        self._loading = was_loading

    @staticmethod
    def _select(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def load(self) -> None:
        self._loading = True
        cfg = self._controller.load()
        self.port.setCurrentText(cfg.serial_port)
        self._select(self.baudrate, cfg.baudrate)
        self._select(self.data_bits, cfg.data_bits)
        self._select(self.parity, cfg.parity)
        self._select(self.stop_bits, cfg.stop_bits)
        self.transmissions.setValue(cfg.serial_transmissions)
        self.header_1.setValue(cfg.serial_header_1)
        self.header_2.setValue(cfg.serial_header_2)
        self._update_preview()
        self._select(self.printer_type, cfg.printer_type)
        self.printer_port.setText(cfg.printer_port)
        self.print_tickets.setChecked(cfg.print_tickets)
        self._loading = False
        self.action_bar.set_dirty(False)

    def save(self) -> bool:
        try:
            self._controller.update(
                serial_port=self.port.currentText().strip(),
                baudrate=self.baudrate.currentData(),
                data_bits=self.data_bits.currentData(),
                parity=self.parity.currentData(),
                stop_bits=self.stop_bits.currentData(),
                serial_transmissions=self.transmissions.value(),
                serial_header_1=self.header_1.value(),
                serial_header_2=self.header_2.value(),
                printer_type=self.printer_type.currentData(),
                printer_port=self.printer_port.text().strip(),
                print_tickets=self.print_tickets.isChecked(),
            )
        except ValueError as exc:
            self.action_bar.show_result(f"No guardado: {exc}", "err")
            return False
        self.action_bar.show_result("Configuración de hardware guardada.", "ok")
        return True
