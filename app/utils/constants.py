import os
import sys
from pathlib import Path

APP_NAME = "Turnos Desktop"
APP_VERSION = "0.1.0"


def resolve_base_dir() -> Path:
    """Carpeta (escribible) de `database/` y `logs/`.

    - `TURNOS_HOME` manda siempre.
    - Empaquetado (PyInstaller): `%LOCALAPPDATA%\\TurnosDesktop`. La carpeta de la app no sirve:
      puede ser de solo lectura o temporal, y los datos deben sobrevivir a actualizaciones.
    - Desarrollo: la raíz del repositorio.
    """
    override = os.environ.get("TURNOS_HOME")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        root = os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share"
        return Path(root) / "TurnosDesktop"
    return Path(__file__).resolve().parents[2]


BASE_DIR = resolve_base_dir()
DATABASE_PATH = BASE_DIR / "database" / "turnos.db"
LOG_PATH = BASE_DIR / "logs" / "app.log"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 5

# Protocolo serial (compatibilidad con el sistema actual)
SERIAL_HEADER_1 = 0x99
SERIAL_HEADER_2 = 0x55
MIN_TURN = 1
MAX_TURN = 255  # el turno ocupa 1 byte

# Estados de turno
STATUS_RECEIVED = "RECEIVED"
STATUS_PROCESSING = "PROCESSING"
STATUS_SENT = "SENT"
STATUS_PRINTED = "PRINTED"
STATUS_COMPLETED = "COMPLETED"
STATUS_ERROR = "ERROR"
TURN_STATUSES = (
    STATUS_RECEIVED,
    STATUS_PROCESSING,
    STATUS_SENT,
    STATUS_PRINTED,
    STATUS_COMPLETED,
    STATUS_ERROR,
)
# Turnos no finalizados: requieren proceso, verificación o reintento (todo menos COMPLETED).
PENDING_STATUSES = (
    STATUS_RECEIVED,
    STATUS_PROCESSING,
    STATUS_SENT,
    STATUS_PRINTED,
    STATUS_ERROR,
)

DEFAULT_TERMINAL_ID = "TERM-001"  # solo para desarrollo con el Mock HUB

# Tipos de evento
EVENT_HUB_CONNECTED = "HUB_CONNECTED"
EVENT_HUB_DISCONNECTED = "HUB_DISCONNECTED"
EVENT_TURN_RECEIVED = "TURN_RECEIVED"
EVENT_TURN_COMPLETED = "TURN_COMPLETED"
EVENT_SERIAL_CONNECTED = "SERIAL_CONNECTED"
EVENT_SERIAL_ERROR = "SERIAL_ERROR"
EVENT_PRINT_ERROR = "PRINT_ERROR"
EVENT_TURN_DUPLICATE = "TURN_DUPLICATE"
EVENT_TURN_REJECTED = "TURN_REJECTED"
EVENT_TURN_RECOVERED = "TURN_RECOVERED"
