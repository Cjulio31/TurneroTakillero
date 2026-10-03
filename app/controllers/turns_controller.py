import logging

from app.database.turn_repository import TurnRepository
from app.models.turn import Turn

log = logging.getLogger(__name__)


class TurnsController:
    """Turnos pendientes. El reintento real lo conectará TurnService (Fases 4-6)."""

    def __init__(self, turns: TurnRepository):
        self._turns = turns

    def pending(self) -> list[Turn]:
        return self._turns.list_pending()

    def retry(self, message_id: str) -> bool:
        log.info("Reintento solicitado para %s (aún sin TurnService)", message_id)
        return False
