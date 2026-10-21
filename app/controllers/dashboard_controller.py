from collections.abc import Callable

from app.controllers.app_state import AppState
from app.database.turn_repository import TurnRepository
from app.models.configuration import Configuration
from app.models.turn import Turn
from app.services.health_service import HealthReport, HealthService


class DashboardController:
    def __init__(
        self,
        state: AppState,
        turns: TurnRepository,
        health: HealthService | None = None,
        config: Callable[[], Configuration] | None = None,
    ):
        self.state = state
        self._turns = turns
        self._health = health
        self._config = config

    def health_report(self) -> HealthReport | None:
        return self._health.report() if self._health else None

    def on_health_changed(self, slot: Callable[[HealthReport], None]) -> None:
        """Avisa cuando cambia el informe de salud (si hay servicio de salud)."""
        if self._health is not None:
            self._health.report_changed.connect(slot)

    def last_turn(self) -> Turn | None:
        return self._turns.last()

    def terminal_label(self) -> str:
        """Texto de cabecera: 'Terminal TERM-001 · Caja 1'."""
        cfg = self._config() if self._config else None
        if cfg is None or not cfg.terminal_id:
            return "Terminal sin configurar"
        name = f" · {cfg.terminal_name}" if cfg.terminal_name else ""
        return f"Terminal {cfg.terminal_id}{name}"

    def details(self) -> dict[str, str]:
        """Línea secundaria de cada tarjeta de componente."""
        cfg = self._config() if self._config else None
        if cfg is None:
            return {}
        serial = f"{cfg.serial_port or 'sin puerto'} · {cfg.baudrate}"
        printing = "Impresión de tiquetes activa" if cfg.print_tickets else "Impresión desactivada"
        return {
            "hub": cfg.hub_url or "HUB simulado",
            "serial": serial,
            "printer": printing,
            "database": "Respondiendo",
        }
