import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.utils import constants

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(log_path: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    """Configura el logger raíz con rotación (5 MB x 5 archivos). Idempotente."""
    path = Path(log_path or constants.LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, "_turnos_handler", False):
            root.removeHandler(handler)
            handler.close()

    file_handler = RotatingFileHandler(
        path,
        maxBytes=constants.LOG_MAX_BYTES,
        backupCount=constants.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    file_handler._turnos_handler = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
