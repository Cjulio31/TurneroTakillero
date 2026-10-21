from app.controllers import app_state as st
from app.controllers.config_controller import ConfigController
from app.controllers.diagnostics_controller import DiagnosticsController
from app.ui.main_window import PAGES, MainWindow


def test_main_window_has_all_pages(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    assert [window.menu.item(i).text() for i in range(window.menu.count())] == list(PAGES)
    assert window.stack.count() == len(PAGES)


def test_dashboard_reflects_last_turn_and_status(qtbot, ctx):
    ctx.turns.add("A", "TERM-001", 25)
    ctx.turns.update_status("A", "COMPLETED")
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    dash = window.pages["Inicio"]
    assert dash._number.text() == "025"
    assert dash._turn_status.text() == "COMPLETADO"

    ctx.state.set_status("hub", st.CONNECTED)
    assert "CONECTADO" in dash._indicators["hub"].text()
    ctx.state.set_status("hub", st.DISCONNECTED)
    assert "DESCONECTADO" in dash._indicators["hub"].text()


def test_history_filters(qtbot, ctx):
    ctx.turns.add("A", "TERM-001", 1)
    ctx.turns.add("B", "TERM-001", 2)
    ctx.turns.update_status("B", "ERROR", "PRINT", "sin papel")
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    page = window.pages["Historial"]
    assert page.table.rowCount() == 2
    page.status.setCurrentIndex(page.status.findData("ERROR"))
    page.refresh()
    assert page.table.rowCount() == 1
    assert page.table.item(0, 6).text() == "sin papel"


def test_pending_turns_page(qtbot, ctx):
    ctx.turns.add("A", "TERM-001", 1)
    ctx.turns.add("B", "TERM-001", 2)
    ctx.turns.update_status("B", "COMPLETED")
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    assert window.pages["Turnos"].table.rowCount() == 1


def test_configuration_save_and_validation(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    page = window.pages["Configuración"]
    page.hub_url.setText("https://hub.test")
    page.terminal_id.setText("")
    assert page.save() is False
    assert page.action_bar.title.startswith("No guardado")  # el error se ve en la propia barra

    page.terminal_id.setText("TERM-001")
    assert page.save() is True
    cfg = ctx.config_service.load()
    assert (cfg.hub_url, cfg.terminal_id) == ("https://hub.test", "TERM-001")


def test_hardware_save(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    page = window.pages["Hardware"]
    page.port.setCurrentText("COM3")
    page.transmissions.setValue(2)
    page.printer_type.setCurrentIndex(page.printer_type.findData("USB"))
    assert page.save()
    cfg = ctx.config_service.load()
    assert (cfg.serial_port, cfg.baudrate, cfg.serial_transmissions, cfg.printer_type) == (
        "COM3",
        9600,
        2,
        "USB",
    )


def test_diagnostics(ctx):
    ctrl = DiagnosticsController(ctx.state, ctx.db)
    assert ctrl.check_database().ok
    assert not ctrl.send_test_turn(0).ok
    assert "no está activo" in ctrl.send_test_turn(25).message


def test_config_validation_rules():
    from app.models.configuration import Configuration

    try:
        ConfigController.validate(Configuration(hub_url="ftp://x", terminal_id="T"))
    except ValueError as exc:
        assert "URL" in str(exc)
    else:
        raise AssertionError("debió fallar")


def test_close_hides_to_tray_when_available(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.tray.available = True
    window.show()
    window.close()
    assert not window.isVisible()
    assert not window._quitting


def test_mock_hub_page_controls(qtbot, ctx):
    from app.communication.backoff import BackoffPolicy
    from app.communication.mock_hub_client import MockHubClient
    from app.services.hub_service import HubService

    hub = HubService(MockHubClient("TERM-001"), ctx.state, ctx.events, BackoffPolicy([0.01]))
    window = MainWindow(ctx, hub)
    qtbot.addWidget(window)
    assert window.menu.item(window.menu.count() - 1).text() == "Mock HUB"
    page = window.pages["Mock HUB"]
    got = []
    hub.turn_received.connect(got.append)
    hub.start()
    page.turn.setValue(25)
    page.buttons["ENVIAR"].click()
    page.buttons["REENVIAR (duplicado)"].click()
    assert [m["turn"] for m in got] == [25, 25]
    assert got[0]["message_id"] == got[1]["message_id"]
    page.buttons["DESCONECTAR"].click()
    assert not hub.client.is_connected()
    page.buttons["RECONECTAR"].click()
    assert hub.client.is_connected()
    hub.stop()


def test_turns_page_retry_uses_turn_service(qtbot, ctx, monkeypatch):
    from app.services.errors import PrintError
    from app.services.turn_service import TurnService
    from app.ui import dialogs

    monkeypatch.setattr(dialogs, "confirm", lambda *_: True)

    class Printer:
        fail = True

        def print_ticket(self, turn):
            if self.fail:
                raise PrintError("sin papel")

    class Serial:
        def send_turn(self, n):
            pass

    printer = Printer()
    service = TurnService(
        ctx.turns,
        ctx.events,
        ctx.state,
        Serial(),
        printer,
        ack_sender=lambda *_: True,
        terminal_id=lambda: "TERM-001",
    )
    window = MainWindow(ctx, None, service)
    qtbot.addWidget(window)
    service.handle_message({"message_id": "A", "terminal_id": "TERM-001", "turn": 25})
    page = window.pages["Turnos"]
    assert page.table.rowCount() == 1 and page.table.item(0, 2).text() == "ERROR"

    printer.fail = False
    page.table.selectRow(0)
    page.retry_button.click()
    assert ctx.turns.get_by_message_id("A").status == "COMPLETED"
    assert page.table.rowCount() == 0
    assert "completado" in page.message.text().lower()


def test_self_check_passes(tmp_path, monkeypatch):
    from app import main as app_main

    monkeypatch.setattr("app.utils.constants.DATABASE_PATH", tmp_path / "db" / "t.db")
    monkeypatch.setattr("app.utils.constants.LOG_PATH", tmp_path / "logs" / "app.log")
    assert app_main.main(["--self-check"]) == 0


def test_diagnostics_clear_logs(qtbot, ctx, tmp_path, monkeypatch):
    from app.ui.diagnostics import DiagnosticsPage
    from app.utils import constants
    from app.utils.logger import setup_logging

    path = tmp_path / "logs" / "app.log"
    monkeypatch.setattr(constants, "LOG_PATH", path)
    setup_logging(path)
    import logging

    logging.getLogger("t").info("linea vieja")
    page = DiagnosticsPage(DiagnosticsController(ctx.state, ctx.db))
    qtbot.addWidget(page)
    page.load_logs()
    assert "linea vieja" in page.log_view.toPlainText()
    page.clear_logs(confirm=False)
    assert "linea vieja" not in page.log_view.toPlainText()
    assert page.result.text().startswith("Logs borrados")
    assert ctx.turns.last() is None  # no toca los datos


def test_turns_page_retry_needs_error_selection_and_confirmation(qtbot, ctx, monkeypatch):
    from app.services.errors import PrintError
    from app.services.turn_service import TurnService
    from app.ui import dialogs

    class Printer:
        def print_ticket(self, turn):
            raise PrintError("sin papel")

    class Serial:
        def send_turn(self, n):
            pass

    service = TurnService(
        ctx.turns,
        ctx.events,
        ctx.state,
        Serial(),
        Printer(),
        ack_sender=lambda *_: True,
        terminal_id=lambda: "TERM-001",
    )
    window = MainWindow(ctx, None, service)
    qtbot.addWidget(window)
    page = window.pages["Turnos"]
    assert not page.retry_button.isEnabled()  # nada seleccionado

    service.handle_message({"message_id": "A", "terminal_id": "TERM-001", "turn": 25})
    assert not page.retry_button.isEnabled()  # hay un turno, pero no seleccionado
    page.table.selectRow(0)
    assert page.retry_button.isEnabled()  # turno en ERROR seleccionado

    asked = []
    monkeypatch.setattr(dialogs, "confirm", lambda *args: asked.append(args) or False)
    page.retry_button.click()
    assert asked and "25" in asked[0][2]
    assert ctx.turns.get_by_message_id("A").status == "ERROR"  # al decir "No" no se reintenta
    assert page.message.text() == ""


def test_diagnostics_test_turn_asks_before_sending(qtbot, ctx, monkeypatch):
    from app.ui import dialogs
    from app.ui.diagnostics import DiagnosticsPage

    sent = []

    class FakeController(DiagnosticsController):
        def send_test_turn(self, turn_number):
            sent.append(turn_number)
            return super().send_test_turn(turn_number)

    page = DiagnosticsPage(FakeController(ctx.state, ctx.db))
    qtbot.addWidget(page)
    monkeypatch.setattr(dialogs, "confirm", lambda *_: False)
    page.send_test_turn()
    assert sent == []  # al decir "No" no se envía nada al serial
    monkeypatch.setattr(dialogs, "confirm", lambda *_: True)
    page.send_test_turn()
    assert sent == [25]


def test_hardware_page_saves_print_tickets_flag(qtbot, ctx):
    from app.controllers.config_controller import ConfigController
    from app.ui.hardware import HardwarePage

    controller = ConfigController(ctx.config_service)
    page = HardwarePage(controller)
    qtbot.addWidget(page)
    assert page.print_tickets.isChecked()  # por defecto imprime
    page.print_tickets.setChecked(False)
    assert page.save()
    assert ctx.config_service.load().print_tickets is False
    reopened = HardwarePage(controller)
    qtbot.addWidget(reopened)
    assert not reopened.print_tickets.isChecked()


def test_hardware_page_shows_and_saves_serial_header(qtbot, ctx):
    from app.controllers.config_controller import ConfigController
    from app.ui.hardware import HardwarePage

    controller = ConfigController(ctx.config_service)
    page = HardwarePage(controller)
    qtbot.addWidget(page)
    assert (page.header_1.value(), page.header_2.value()) == (153, 85)
    assert page.transmissions.value() == 1
    assert page.packet_preview.text() == "99 55 <turno>"
    page.header_1.setValue(16)
    assert page.packet_preview.text() == "10 55 <turno>"
    assert page.save()
    cfg = ctx.config_service.load()
    assert (cfg.serial_header_1, cfg.serial_header_2) == (16, 85)
