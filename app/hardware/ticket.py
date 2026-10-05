from dataclasses import dataclass
from datetime import datetime

from app.models.turn import Turn


@dataclass(frozen=True)
class Ticket:
    """Contenido imprimible, independiente del método de impresión."""

    header: tuple[str, ...]
    turn_label: str
    footer: tuple[str, ...]


def _clean(*lines: str) -> tuple[str, ...]:
    return tuple(line for line in (s.strip() for s in lines) if line)


def build_ticket(
    turn: Turn, terminal_name: str = "", terminal_location: str = "", now: datetime | None = None
) -> Ticket:
    now = now or datetime.now()
    return Ticket(
        header=_clean(terminal_name, terminal_location),
        turn_label=f"{turn.turn_number:03d}",
        footer=(now.strftime("%Y-%m-%d %H:%M:%S"),),
    )


def build_test_ticket(
    terminal_name: str = "", terminal_location: str = "", now: datetime | None = None
) -> Ticket:
    """Ticket de prueba: no corresponde a ningún turno ni toca la secuencia de producción."""
    now = now or datetime.now()
    return Ticket(
        header=_clean(terminal_name, terminal_location, "*** PRUEBA DE IMPRESORA ***"),
        turn_label="000",
        footer=(now.strftime("%Y-%m-%d %H:%M:%S"), "Ticket de prueba, sin validez"),
    )
