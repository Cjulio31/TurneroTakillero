import uuid

from app.utils import constants


def is_valid_message_id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_valid_uuid(value: object) -> bool:
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


def is_valid_turn(value: object) -> bool:
    """El turno debe ser un entero (no bool) dentro del rango de 1 byte."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and constants.MIN_TURN <= value <= constants.MAX_TURN
    )
