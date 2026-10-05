from app.controllers.app_state import AppState
from app.database.turn_repository import TurnRepository
from app.models.turn import Turn
from app.services.health_service import HealthReport, HealthService


class DashboardController:
    def __init__(self, state: AppState, turns: TurnRepository, health: HealthService | None = None):
        self.state = state
        self._turns = turns
        self._health = health

    def health_report(self) -> HealthReport | None:
        return self._health.report() if self._health else None

    def last_turn(self) -> Turn | None:
        return self._turns.last()
