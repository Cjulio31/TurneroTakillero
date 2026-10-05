from datetime import datetime

import pytest
from PySide6.QtPrintSupport import QPrinter

from app.controllers import app_state as st
from app.controllers.diagnostics_controller import DiagnosticsController
from app.hardware.printer_backend import (
    SimulatedBackend,
    UnsupportedBackend,
    WindowsPrinterBackend,
    create_backend,
)
from app.hardware.ticket import build_test_ticket, build_ticket
from app.models.configuration import Configuration
from app.models.turn import Turn
from app.services.errors import PrintError
from app.services.printer_service import PrinterService

NOW = datetime(2026, 1, 2, 3, 4, 5)


def make_turn(n=25):
    return Turn(message_id="A", terminal_id="T1", turn_number=n, status="SENT", received_at="x")


class FakeBackend:
    def __init__(self):
        self.available = True
        self.error: Exception | None = None
        self.tickets = []

    def is_available(self):
        return self.available

    def print_ticket(self, ticket):
        if self.error:
            raise self.error
        self.tickets.append(ticket)


class Env:
    def __init__(self, ctx):
        self.cfg = Configuration(terminal_name="Caja 1", terminal_location="Piso 2")
        self.backend = FakeBackend()
        self.created: list[tuple[str, str]] = []

        def factory(kind, port):
            self.created.append((kind, port))
            return self.backend

        self.ctx = ctx
        self.service = PrinterService(
            ctx.state, ctx.events, lambda: self.cfg, backend_factory=factory
        )


@pytest.fixture
def env(ctx):
    return Env(ctx)


def test_ticket_content():
    t = build_ticket(make_turn(7), "Caja 1", " ", NOW)
    assert t.header == ("Caja 1",) and t.turn_label == "007"
    assert t.footer == ("2026-01-02 03:04:05",)
    test = build_test_ticket("Caja 1", "", NOW)
    assert "*** PRUEBA DE IMPRESORA ***" in test.header and test.turn_label == "000"


def test_print_ticket_uses_config_header(env):
    env.service.print_ticket(make_turn(25))
    ticket = env.backend.tickets[0]
    assert ticket.header == ("Caja 1", "Piso 2") and ticket.turn_label == "025"


def test_status_follows_availability(env):
    assert env.service.refresh_status() is True
    assert env.ctx.state.status("printer") == st.AVAILABLE
    env.backend.available = False
    assert env.service.refresh_status() is False
    assert env.ctx.state.status("printer") == st.UNAVAILABLE


def test_disconnected_printer_raises_print_error_and_updates_status(env):
    env.backend.available = False
    env.backend.error = PrintError("Impresora no disponible")
    with pytest.raises(PrintError):
        env.service.print_ticket(make_turn())
    assert env.ctx.state.status("printer") == st.UNAVAILABLE
    # el turno lo registra TurnService: el servicio no duplica el evento
    assert env.ctx.events.recent() == []


def test_unexpected_backend_error_becomes_print_error(env):
    env.backend.error = RuntimeError("boom")
    with pytest.raises(PrintError, match="boom"):
        env.service.print_ticket(make_turn())


def test_backend_recreated_only_when_config_changes(env):
    env.service.refresh_status()
    env.service.refresh_status()
    assert env.created == [("", "")]
    env.cfg = Configuration(printer_type="Windows Printer", printer_port="POS")
    env.service.on_config_changed()
    assert env.created[-1] == ("Windows Printer", "POS")


def test_test_print_failure_is_logged_as_event(env):
    env.backend.error = PrintError("sin papel")
    with pytest.raises(PrintError):
        env.service.test()
    assert any("prueba" in e["message"] for e in env.ctx.events.recent())


def test_diagnostics_printer(env):
    diag = DiagnosticsController(env.ctx.state, env.ctx.db, printer=env.service)
    assert diag.test_printer().ok and len(env.backend.tickets) == 1
    env.backend.error = PrintError("sin papel")
    result = diag.test_printer()
    assert not result.ok and "sin papel" in result.message
    env.backend.available = False
    assert diag.test_printer().message == "Impresora no disponible"
    assert not DiagnosticsController(env.ctx.state, env.ctx.db).test_printer().ok


def test_backend_factory():
    assert isinstance(create_backend(""), SimulatedBackend)
    assert isinstance(create_backend("Windows Printer", "X"), WindowsPrinterBackend)
    usb = create_backend("USB")
    assert isinstance(usb, UnsupportedBackend) and not usb.is_available()
    with pytest.raises(PrintError, match="USB"):
        usb.print_ticket(build_test_ticket())


def test_windows_backend_missing_printer_is_unavailable():
    backend = WindowsPrinterBackend("no-existe-xyz")
    assert not backend.is_available()
    with pytest.raises(PrintError, match="no disponible"):
        backend.print_ticket(build_test_ticket())


def test_windows_backend_renders_to_pdf(tmp_path):
    out = tmp_path / "ticket.pdf"

    def factory():
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(out))
        return printer

    WindowsPrinterBackend(printer_factory=factory).print_ticket(
        build_ticket(make_turn(25), "Caja 1", "Piso 2", NOW)
    )
    assert out.read_bytes().startswith(b"%PDF")
