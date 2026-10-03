from typing import Any

from app.models.hub_message import TurnMessage
from app.utils.validators import is_valid_message_id, is_valid_turn

# Códigos de rechazo
MALFORMED = "MALFORMED"
MISSING_MESSAGE_ID = "MISSING_MESSAGE_ID"
MISSING_TERMINAL_ID = "MISSING_TERMINAL_ID"
WRONG_TERMINAL = "WRONG_TERMINAL"
MISSING_TURN = "MISSING_TURN"
INVALID_TURN = "INVALID_TURN"


class MessageRejected(Exception):
    def __init__(self, code: str, reason: str, message_id: str | None = None):
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason
        self.message_id = message_id


def parse_message(payload: Any, terminal_id: str) -> TurnMessage:
    """Valida un mensaje crudo del HUB, en el orden de la especificación.

    La detección de duplicados necesita la BD y la hace TurnService.
    """
    if not isinstance(payload, dict):
        raise MessageRejected(MALFORMED, "El mensaje no es un objeto")

    raw_id = payload.get("message_id")
    message_id = raw_id if isinstance(raw_id, str) else None
    if not is_valid_message_id(raw_id):
        raise MessageRejected(MISSING_MESSAGE_ID, "Falta message_id")

    msg_terminal = payload.get("terminal_id")
    if not isinstance(msg_terminal, str) or not msg_terminal.strip():
        raise MessageRejected(MISSING_TERMINAL_ID, "Falta terminal_id", message_id)
    if msg_terminal != terminal_id:
        raise MessageRejected(
            WRONG_TERMINAL, f"Terminal destino {msg_terminal} != {terminal_id}", message_id
        )

    if payload.get("turn") is None:
        raise MessageRejected(MISSING_TURN, "Falta el turno", message_id)
    turn = payload["turn"]
    if not is_valid_turn(turn):
        raise MessageRejected(INVALID_TURN, f"Turno inválido: {turn!r} (1-255)", message_id)

    priority = payload.get("priority")
    created_at = payload.get("created_at")
    metadata = payload.get("metadata")
    return TurnMessage(
        message_id=message_id,
        terminal_id=msg_terminal,
        turn=turn,
        priority=priority if isinstance(priority, int) and not isinstance(priority, bool) else 0,
        created_at=created_at if isinstance(created_at, str) else None,
        metadata=metadata if isinstance(metadata, dict) else {},
    )
