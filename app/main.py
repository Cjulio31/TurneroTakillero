import logging

from app.database.config_repository import ConfigRepository
from app.database.database import Database
from app.database.event_repository import EventRepository
from app.database.turn_repository import TurnRepository
from app.services.configuration_service import ConfigurationService
from app.utils import constants
from app.utils.logger import setup_logging

log = logging.getLogger(__name__)


def bootstrap() -> dict:
    """Inicializa logging, base de datos y servicios base (Fase 1; aún sin UI)."""
    setup_logging()
    log.info("Iniciando %s %s", constants.APP_NAME, constants.APP_VERSION)
    db = Database()
    return {
        "db": db,
        "config": ConfigurationService(ConfigRepository(db)),
        "turns": TurnRepository(db),
        "events": EventRepository(db),
    }


def main() -> int:
    ctx = bootstrap()
    log.info("Base de datos lista en %s (ok=%s)", ctx["db"].path, ctx["db"].is_ok())
    ctx["db"].close()
    return 0
