from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnMessage:
    message_id: str
    terminal_id: str
    turn: int
    priority: int = 0
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
