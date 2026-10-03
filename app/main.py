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
from app.hardware.simulated import SimulatedPrinter, SimulatedSerial
from app.services.configuration_service import ConfigurationService
from app.services.hub_service import HubService
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
        config_service=ConfigurationService(ConfigRepository(db)),
        turns=TurnRepository(db),
        events=EventRepository(db),
        state=AppState(),
    )


def main() -> int:
    ctx = bootstrap()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # sigue en la bandeja al cerrar la ventana
    # Hasta las fases 5-7 se usan HUB, serial e impresora simulados.
    terminal_id = ctx.config_service.load().terminal_id or constants.DEFAULT_TERMINAL_ID
    hub = HubService(MockHubClient(terminal_id), ctx.state, ctx.events)
    turn_service = TurnService(
        ctx.turns,
        ctx.events,
        ctx.state,
        serial=SimulatedSerial(),
        printer=SimulatedPrinter(),
        ack_sender=hub.send_ack,
        terminal_id=lambda: ctx.config_service.load().terminal_id or constants.DEFAULT_TERMINAL_ID,
    )
    hub.turn_received.connect(turn_service.handle_message)
    turn_service.startup()  # recupera turnos pendientes del cierre anterior
    window = MainWindow(ctx, hub, turn_service)
    window.show()
    hub.start()
    code = app.exec()
    hub.stop()
    ctx.db.close()
    return code
