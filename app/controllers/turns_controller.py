import logging

from app.database.turn_repository import TurnRepository
from app.models.turn import Turn
from app.services import turn_service as ts
from app.services.turn_service import TurnService

log = logging.getLogger(__name__)

# Resultado del reintento -> (texto para el usuario, nivel visual)
_RETRY_TEXT = {
    ts.OUTCOME_COMPLETED: ("Turno reintentado: completado.", "ok"),
    ts.OUTCOME_PENDING: ("El serial no está disponible: el turno quedó pendiente.", "warn"),
    ts.OUTCOME_ERROR: ("El reintento falló: el turno sigue en ERROR.", "err"),
    ts.OUTCOME_DUPLICATE: ("El turno ya estaba procesado.", "warn"),
    ts.OUTCOME_REJECTED: ("El turno fue rechazado.", "err"),
}


class TurnsController:
    """Turnos pendientes y reintento manual (mismo message_id)."""

    def __init__(self, turns: TurnRepository, service: TurnService | None = None):
        self._turns = turns
        self._service = service

    def pending(self) -> list[Turn]:
        return self._turns.list_pending()

    def retry(self, message_id: str) -> tuple[str, str]:
        """Reintenta un turno. Devuelve (texto para el usuario, nivel: ok/warn/err)."""
        if self._service is None:
            return "El procesamiento de turnos no está activo", "warn"
        result = self._service.retry(message_id)
        if result is None:
            return "Solo se pueden reintentar turnos en ERROR", "warn"
        return _RETRY_TEXT.get(result.outcome, (f"Resultado: {result.outcome}", "warn"))
