import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.database.database import Database


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def ctx(db):
    from app.context import AppContext
    from app.controllers.app_state import AppState
    from app.database.config_repository import ConfigRepository
    from app.database.event_repository import EventRepository
    from app.database.turn_repository import TurnRepository
    from app.services.configuration_service import ConfigurationService

    return AppContext(
        db=db,
        config_service=ConfigurationService(ConfigRepository(db)),
        turns=TurnRepository(db),
        events=EventRepository(db),
        state=AppState(),
    )
