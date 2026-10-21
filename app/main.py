import logging
import sys

import keyring
from PySide6.QtPrintSupport import QPrinterInfo
from PySide6.QtWidgets import QApplication, QMessageBox

from app.communication.mock_hub_client import MockHubClient
from app.context import AppContext
from app.controllers.app_state import AppState
from app.database.config_repository import ConfigRepository
from app.database.database import Database
from app.database.event_repository import EventRepository
from app.database.turn_repository import TurnRepository
from app.hardware.serial_device import SerialSettings, list_serial_ports
from app.services.autostart import MINIMIZED_FLAG, create_autostart
from app.services.configuration_service import ConfigurationService
from app.services.health_service import HealthService
from app.services.hub_service import HubService
from app.services.printer_service import PrinterService
from app.services.secret_store import KeyringSecretStore
from app.services.serial_service import SerialService
from app.services.turn_service import TurnService
from app.ui import icons
from app.ui.icons import app_icon
from app.ui.main_window import MainWindow
from app.ui.theme import theme
from app.utils import constants
from app.utils.logger import install_excepthook, setup_logging
from app.utils.single_instance import SingleInstance

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


def self_check() -> int:
    """Verifica que el ejecutable empaquetado arranca con todas sus dependencias (0 = OK).

    Pensado para probar una instalación limpia sin abrir la ventana: carga Qt (plugins), crea
    la interfaz completa, abre la base de datos y consulta serial, impresión y keyring.
    El resultado queda en el log (el .exe de Windows no tiene consola).
    """
    try:
        ctx = bootstrap()
        app = QApplication.instance() or QApplication(sys.argv)
        MainWindow(ctx)  # construye todas las pantallas sin mostrarlas
        checks = {
            "database": ctx.db.is_ok(),
            "serial_ports": list_serial_ports() is not None,
            "printers": QPrinterInfo.availablePrinterNames() is not None,
            "keyring": keyring.get_keyring().priority > 0 or sys.platform != "win32",
            "icons": not app_icon().isNull() and not icons.pixmap("check", "#000000").isNull(),
        }
        ctx.db.close()
        del app
    except Exception:
        log.exception("SELF-CHECK failed")
        return 1
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        log.error("SELF-CHECK failed: %s", ", ".join(failed))
        return 1
    log.info("SELF-CHECK OK (data dir: %s)", constants.BASE_DIR)
    return 0


def main(argv: list[str] | None = None) -> int:
    install_excepthook()
    args = sys.argv[1:] if argv is None else argv
    if "--self-check" in args:
        return self_check()
    app = QApplication.instance() or QApplication(sys.argv)
    instance = SingleInstance(constants.LOCK_PATH)
    if not instance.acquire():
        setup_logging()
        log.warning("Ya hay otra instancia de %s en ejecución", constants.APP_NAME)
        QMessageBox.warning(
            None,
            constants.APP_NAME,
            f"{constants.APP_NAME} ya está en ejecución.\nRevise la bandeja del sistema.",
        )
        return 1
    ctx = bootstrap()
    app.setApplicationName(constants.APP_NAME)
    app.setWindowIcon(app_icon())
    theme.set_mode(ctx.config_service.load().theme, app)  # claro por defecto
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
        print_enabled=lambda: ctx.config_service.load().print_tickets,
    )
    hub.turn_received.connect(turn_service.handle_message)
    turn_service.startup()  # recupera turnos pendientes del cierre anterior
    health = HealthService(ctx.state, ctx.db, ctx.turns)
    window = MainWindow(ctx, hub, turn_service, serial, printer, health, create_autostart())
    # Iniciada con Windows (--minimized) arranca oculta en la bandeja, si la bandeja existe.
    if not (MINIMIZED_FLAG in args and window.tray.available):
        window.show()
    serial.start()
    printer.start()
    health.start()
    hub.start()
    code = app.exec()
    hub.stop()
    serial.stop()
    printer.stop()
    health.stop()
    ctx.db.close()
    instance.release()
    return code
