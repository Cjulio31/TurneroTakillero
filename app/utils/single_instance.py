from pathlib import Path

from PySide6.QtCore import QLockFile


class SingleInstance:
    """Impide dos instancias de la app: compartirían SQLite y se disputarían el puerto serial.

    Usa un archivo de bloqueo; si el proceso muere sin liberarlo, Qt detecta el bloqueo huérfano.
    """

    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._lock = QLockFile(str(self._path))

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        return self._lock.tryLock(0)

    def release(self) -> None:
        self._lock.unlock()
