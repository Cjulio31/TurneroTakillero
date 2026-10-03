from app.controllers.app_state import AppState
from app.database.turn_repository import TurnRepository
from app.models.turn import Turn


class DashboardController:
    def __init__(self, state: AppState, turns: TurnRepository):
        self.state = state
        self._turns = turns

    def last_turn(self) -> Turn | None:
        return self._turns.last()
