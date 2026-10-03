from dataclasses import dataclass

from app.controllers.app_state import AppState
from app.database.database import Database
from app.database.event_repository import EventRepository
from app.database.turn_repository import TurnRepository
from app.services.configuration_service import ConfigurationService


@dataclass
class AppContext:
    db: Database
    config_service: ConfigurationService
    turns: TurnRepository
    events: EventRepository
    state: AppState
