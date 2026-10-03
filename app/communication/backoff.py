from collections.abc import Sequence

DEFAULT_DELAYS = (5, 10, 20, 30, 60)  # segundos; el último es el máximo


class BackoffPolicy:
    """Espera creciente entre intentos de reconexión; se queda en el último valor."""

    def __init__(self, delays: Sequence[float] = DEFAULT_DELAYS):
        if not delays:
            raise ValueError("delays no puede estar vacío")
        self._delays = tuple(delays)
        self._attempt = 0

    @property
    def attempt(self) -> int:
        return self._attempt

    def next_delay(self) -> float:
        delay = self._delays[min(self._attempt, len(self._delays) - 1)]
        self._attempt += 1
        return delay

    def reset(self) -> None:
        self._attempt = 0
