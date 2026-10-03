from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controllers.config_controller import ConfigController

PARITIES = (("None", "N"), ("Even", "E"), ("Odd", "O"))
PRINTER_TYPES = ("", "USB", "Serial", "Windows Printer", "Network Printer")


class HardwarePage(QWidget):
    """Configuración del puerto serial y de la impresora."""

    def __init__(self, controller: ConfigController, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller

        self.port = QComboBox()
        self.port.setEditable(True)
        refresh = QPushButton("Actualizar puertos")
        refresh.clicked.connect(self.refresh_ports)
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

        serial_box = QGroupBox("Serial")
        sform = QFormLayout(serial_box)
        sform.addRow("Puerto", self.port)
        sform.addRow(refresh)
        sform.addRow("Baudrate", self.baudrate)
        sform.addRow("Data bits", self.data_bits)
        sform.addRow("Paridad", self.parity)
        sform.addRow("Stop bits", self.stop_bits)
        sform.addRow("Transmisiones", self.transmissions)

        self.printer_type = QComboBox()
        for t in PRINTER_TYPES:
            self.printer_type.addItem(t or "(sin definir)", t)
        self.printer_port = QLineEdit()
        printer_box = QGroupBox("Impresora")
        pform = QFormLayout(printer_box)
        pform.addRow("Método", self.printer_type)
        pform.addRow("Puerto / nombre / dirección", self.printer_port)

        save = QPushButton("Guardar")
        save.clicked.connect(self.save)
        self.message = QLabel()

        layout = QVBoxLayout(self)
        layout.addWidget(serial_box)
        layout.addWidget(printer_box)
        layout.addWidget(save)
        layout.addWidget(self.message)
        layout.addStretch(1)
        self.refresh_ports()
        self.load()

    def refresh_ports(self) -> None:
        current = self.port.currentText()
        self.port.clear()
        self.port.addItems(self._controller.available_serial_ports())
        self.port.setCurrentText(current)

    @staticmethod
    def _select(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def load(self) -> None:
        cfg = self._controller.load()
        self.port.setCurrentText(cfg.serial_port)
        self._select(self.baudrate, cfg.baudrate)
        self._select(self.data_bits, cfg.data_bits)
        self._select(self.parity, cfg.parity)
        self._select(self.stop_bits, cfg.stop_bits)
        self.transmissions.setValue(cfg.serial_transmissions)
        self._select(self.printer_type, cfg.printer_type)
        self.printer_port.setText(cfg.printer_port)

    def save(self) -> bool:
        try:
            self._controller.update(
                serial_port=self.port.currentText().strip(),
                baudrate=self.baudrate.currentData(),
                data_bits=self.data_bits.currentData(),
                parity=self.parity.currentData(),
                stop_bits=self.stop_bits.currentData(),
                serial_transmissions=self.transmissions.value(),
                printer_type=self.printer_type.currentData(),
                printer_port=self.printer_port.text().strip(),
            )
        except ValueError as exc:
            self.message.setText(f"No guardado: {exc}")
            return False
        self.message.setText("Configuración de hardware guardada.")
        return True
