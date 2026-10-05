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


def clear_logs(log_path: Path | None = None) -> tuple[int, int]:
    """Borra el contenido del log activo y los archivos rotados. Devuelve (archivos, bytes).

    Solo toca los logs (`app.log`, `app.log.1`...), nunca la base de datos. El log activo se vacía
    en lugar de borrarse: el handler lo sigue usando (en Windows un archivo abierto no se puede
    eliminar). Si algún archivo no se puede borrar se registra y se sigue con los demás.
    """
    path = Path(log_path or constants.LOG_PATH)
    handlers = [
        h
        for h in logging.getLogger().handlers
        if getattr(h, "_turnos_handler", False) and Path(h.baseFilename) == path.absolute()
    ]
    for (
        handler
    ) in handlers:  # suelta el archivo mientras se borra; el handler lo reabre al escribir
        handler.acquire()
        if handler.stream is not None:
            handler.stream.close()
            handler.stream = None
    deleted = size = 0
    try:
        for candidate in [path, *sorted(path.parent.glob(path.name + ".*"))]:
            if not candidate.is_file():
                continue
            freed = candidate.stat().st_size
            try:
                if candidate == path:
                    candidate.write_text("")
                else:
                    candidate.unlink()
            except OSError as exc:
                logging.getLogger(__name__).error("No se pudo borrar %s: %s", candidate, exc)
                continue
            deleted += 1
            size += freed
    finally:
        for handler in handlers:
            handler.release()
    logging.getLogger(__name__).info("Logs borrados por el usuario (%s archivo(s))", deleted)
    return deleted, size


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
