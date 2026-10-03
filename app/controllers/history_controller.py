from app.database.turn_repository import TurnRepository
from app.models.turn import Turn
from app.utils import constants


class HistoryController:
    statuses = constants.TURN_STATUSES

    def __init__(self, turns: TurnRepository):
        self._turns = turns

    def search(
        self, date: str | None = None, turn_number: int | None = None, status: str | None = None
    ) -> list[Turn]:
        return self._turns.search(date=date, turn_number=turn_number, status=status or None)
