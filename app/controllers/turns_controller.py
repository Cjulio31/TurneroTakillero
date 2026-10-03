import logging

from app.database.turn_repository import TurnRepository
from app.models.turn import Turn
from app.services.turn_service import TurnService

log = logging.getLogger(__name__)


class TurnsController:
    """Turnos pendientes y reintento manual (mismo message_id)."""

    def __init__(self, turns: TurnRepository, service: TurnService | None = None):
        self._turns = turns
        self._service = service

    def pending(self) -> list[Turn]:
        return self._turns.list_pending()

    def retry(self, message_id: str) -> str:
        """Devuelve un texto para el usuario con el resultado del reintento."""
        if self._service is None:
            return "El procesamiento de turnos no está activo"
        result = self._service.retry(message_id)
        if result is None:
            return "Solo se pueden reintentar turnos en ERROR"
        return f"Reintento: {result.outcome}"
