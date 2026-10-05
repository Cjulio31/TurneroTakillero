import logging
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from app.hardware.ticket import Ticket
from app.services.errors import PrintError

log = logging.getLogger(__name__)

# Valores de `printer_type` (ver PRINTER_TYPES en la pantalla Hardware).
TYPE_NONE = ""
TYPE_WINDOWS = "Windows Printer"


class PrinterBackend(Protocol):
    def is_available(self) -> bool: ...

    def print_ticket(self, ticket: Ticket) -> None:
        """Imprime o lanza PrintError."""


class SimulatedBackend:
    """Sin impresora configurada: solo registra el ticket (desarrollo)."""

    def is_available(self) -> bool:
        return True

    def print_ticket(self, ticket: Ticket) -> None:
        log.info("SIMULATED PRINT: %s | %s", " / ".join(ticket.header), ticket.turn_label)


class UnsupportedBackend:
    """Método aún no implementado (USB/Serial/Red): requiere el modelo real de impresora."""

    def __init__(self, printer_type: str):
        self._type = printer_type

    def is_available(self) -> bool:
        return False

    def print_ticket(self, ticket: Ticket) -> None:
        raise PrintError(f"Método de impresión no implementado: {self._type}")


class WindowsPrinterBackend:
    """Impresora instalada en el sistema (Windows/CUPS) vía Qt. Sin nombre: la predeterminada."""

    def __init__(
        self, name: str = "", printer_factory: Callable[[], QPrinter] | None = None
    ) -> None:
        self._name = name.strip()
        self._factory = printer_factory

    def _target(self) -> str:
        return self._name or QPrinterInfo.defaultPrinterName()

    def is_available(self) -> bool:
        if self._factory is not None:  # destino inyectado (pruebas / PDF)
            return True
        target = self._target()
        return bool(target) and target in QPrinterInfo.availablePrinterNames()

    def print_ticket(self, ticket: Ticket) -> None:
        if not self.is_available():
            raise PrintError(f"Impresora no disponible: {self._target() or '(ninguna)'}")
        if self._factory is not None:
            printer = self._factory()
        else:
            printer = QPrinter(QPrinterInfo.printerInfo(self._target()))
        painter = QPainter()
        if not painter.begin(printer):
            raise PrintError("No se pudo iniciar la impresión")
        try:
            self._draw(painter, printer, ticket)
        finally:
            painter.end()
        if printer.printerState() == QPrinter.PrinterState.Error:
            raise PrintError("La impresora reportó un error")

    @staticmethod
    def _draw(painter: QPainter, printer: QPrinter, ticket: Ticket) -> None:
        page = printer.pageRect(QPrinter.Unit.DevicePixel)
        dpi = max(printer.resolution(), 72)
        unit = dpi / 72  # puntos tipográficos -> píxeles del dispositivo
        y = 0.0

        def line(text: str, points: int, bold: bool = False) -> None:
            nonlocal y
            font = QFont("Sans Serif")
            font.setPixelSize(round(points * unit))
            font.setBold(bold)
            painter.setFont(font)
            height = painter.fontMetrics().height() * 1.2
            rect = QRectF(page.left(), page.top() + y, page.width(), height)
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
            y += height

        for text in ticket.header:
            line(text, 10, bold=True)
        line("TURNO", 12)
        line(ticket.turn_label, 60, bold=True)
        for text in ticket.footer:
            line(text, 8)


def create_backend(printer_type: str, printer_port: str = "") -> PrinterBackend:
    if printer_type == TYPE_NONE:
        return SimulatedBackend()
    if printer_type == TYPE_WINDOWS:
        return WindowsPrinterBackend(printer_port)
    return UnsupportedBackend(printer_type)
