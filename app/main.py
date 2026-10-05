import logging
import sys

from PySide6.QtWidgets import QApplication

from app.communication.mock_hub_client import MockHubClient
from app.context import AppContext
from app.controllers.app_state import AppState
from app.database.config_repository import ConfigRepository
from app.database.database import Database
from app.database.event_repository import EventRepository
from app.database.turn_repository import TurnRepository
from app.hardware.serial_device import SerialSettings
from app.services.configuration_service import ConfigurationService
from app.services.hub_service import HubService
from app.services.printer_service import PrinterService
from app.services.secret_store import KeyringSecretStore
from app.services.serial_service import SerialService
from app.services.turn_service import TurnService
from app.ui.main_window import MainWindow
from app.utils import constants
from app.utils.logger import setup_logging

log = logging.getLogger(__name__)


def bootstrap() -> AppContext:
    """Inicializa logging, base de datos y servicios base."""
    setup_logging()
    log.info("Iniciando %s %s", constants.APP_NAME, constants.APP_VERSION)
    db = Database()
    return AppContext(
        db=db,
        config_service=ConfigurationService(ConfigRepository(db), KeyringSecretStore()),
        turns=TurnRepository(db),
        events=EventRepository(db),
        state=AppState(),
    )


def main() -> int:
    ctx = bootstrap()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # sigue en la bandeja al cerrar la ventana
    # Hasta la fase 7 se usa HUB simulado; serial e impresora ya son servicios reales.
    terminal_id = ctx.config_service.load().terminal_id or constants.DEFAULT_TERMINAL_ID
    hub = HubService(MockHubClient(terminal_id), ctx.state, ctx.events)
    serial = SerialService(
        ctx.state,
        ctx.events,
        settings_provider=lambda: SerialSettings.from_config(ctx.config_service.load()),
    )
    ctx.config_service.add_listener(lambda _cfg: serial.on_config_changed())
    printer = PrinterService(ctx.state, ctx.events, config_provider=ctx.config_service.load)
    ctx.config_service.add_listener(lambda _cfg: printer.on_config_changed())
    turn_service = TurnService(
        ctx.turns,
        ctx.events,
        ctx.state,
        serial=serial,
        printer=printer,
        ack_sender=hub.send_ack,
        terminal_id=lambda: ctx.config_service.load().terminal_id or constants.DEFAULT_TERMINAL_ID,
    )
    hub.turn_received.connect(turn_service.handle_message)
    turn_service.startup()  # recupera turnos pendientes del cierre anterior
    window = MainWindow(ctx, hub, turn_service, serial, printer)
    window.show()
    serial.start()
    printer.start()
    hub.start()
    code = app.exec()
    hub.stop()
    serial.stop()
    printer.stop()
    ctx.db.close()
    return code
