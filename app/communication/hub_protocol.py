"""Formato de mensajes terminal <-> HUB.

PROVISIONAL: se basa en el mensaje de turno ya definido (`message_id`, `terminal_id`, `turn`,
`priority`, `created_at`, `metadata`) y en convenciones habituales. Cuando el equipo del HUB
entregue su especificación (ver docs/HUB_PROTOCOLO.md) solo debe cambiar este módulo: los
transportes y TurnService no conocen el formato de los cuadros.

Cada cuadro WebSocket es un objeto JSON `{"type": ..., ...}`.
"""

import json
from typing import Any

# terminal -> HUB
T_REGISTER = "REGISTER"
T_READY = "READY"
T_ACK = "ACK"
T_PONG = "PONG"
# HUB -> terminal
T_REGISTERED = "REGISTERED"
T_TURN = "TURN"
T_PING = "PING"
T_ERROR = "ERROR"

PROTOCOL_VERSION = 1


def encode(frame_type: str, **fields: Any) -> str:
    return json.dumps({"type": frame_type, **fields}, separators=(",", ":"))


def decode(raw: str | bytes) -> dict[str, Any] | None:
    """Devuelve el cuadro, o None si no es un objeto JSON con `type`."""
    try:
        frame = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(frame, dict) or not isinstance(frame.get("type"), str):
        return None
    return frame


def register_frame(terminal_id: str, name: str, location: str, app_version: str) -> str:
    return encode(
        T_REGISTER,
        terminal_id=terminal_id,
        name=name,
        location=location,
        app_version=app_version,
        protocol=PROTOCOL_VERSION,
    )


def ack_frame(terminal_id: str, message_id: str, status: str) -> str:
    return encode(T_ACK, terminal_id=terminal_id, message_id=message_id, status=status)


def turn_payload(frame: dict[str, Any]) -> dict[str, Any] | None:
    """El mensaje de turno crudo (lo valida TurnService) dentro de un cuadro TURN."""
    data = frame.get("data")
    return data if isinstance(data, dict) else None


def error_info(frame: dict[str, Any]) -> tuple[str, str]:
    return str(frame.get("code") or "HUB_ERROR"), str(frame.get("message") or "")
