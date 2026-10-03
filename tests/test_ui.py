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
    assert page.save(msg_box=False) is False

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
    assert "Fase 5" in ctrl.send_test_turn(25).message


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


def test_turns_page_retry_uses_turn_service(qtbot, ctx):
    from app.services.errors import PrintError
    from app.services.turn_service import TurnService

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
    assert "COMPLETED" in page.message.text()
