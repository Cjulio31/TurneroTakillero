import logging
import sys
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "TurnosDesktop"  # el mismo valor que registra el instalador (TurnosDesktop.iss)
MINIMIZED_FLAG = "--minimized"  # arranca oculta en la bandeja


class AutostartError(OSError):
    """No se pudo leer o cambiar el inicio automático."""


class AutostartStore(Protocol):
    def is_supported(self) -> bool: ...

    def is_enabled(self) -> bool: ...

    def set_enabled(self, enabled: bool) -> None:
        """Activa o desactiva el inicio con el sistema. Lanza AutostartError si falla."""


def default_command() -> str:
    """Comando que Windows ejecuta al iniciar sesión (ejecutable empaquetado o run.py)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" {MINIMIZED_FLAG}'
    interpreter = Path(sys.executable)
    windowless = interpreter.with_name("pythonw.exe")  # sin consola
    if windowless.exists():
        interpreter = windowless
    script = Path(__file__).resolve().parents[2] / "run.py"
    return f'"{interpreter}" "{script}" {MINIMIZED_FLAG}'


class WindowsAutostart:
    """Inicio con Windows mediante HKCU\\...\\Run (no requiere permisos de administrador)."""

    def __init__(self, command: str | None = None):
        self._command = command or default_command()

    def is_supported(self) -> bool:
        return sys.platform == "win32"

    def is_enabled(self) -> bool:
        if not self.is_supported():
            return False
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, VALUE_NAME)
        except FileNotFoundError:
            return False
        except OSError as exc:
            log.error("No se pudo leer el inicio automático: %s", exc)
            return False
        return True

    def set_enabled(self, enabled: bool) -> None:
        if not self.is_supported():
            raise AutostartError("El inicio automático solo está disponible en Windows")
        import winreg

        try:
            if enabled:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                    winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, self._command)
            else:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
                    ) as key:
                        winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass  # ya estaba desactivado
        except OSError as exc:
            log.error("No se pudo cambiar el inicio automático: %s", exc)
            raise AutostartError(str(exc)) from exc
        log.info("Inicio con Windows %s", "activado" if enabled else "desactivado")


class NullAutostart:
    """Plataformas sin inicio automático soportado (y pruebas)."""

    def is_supported(self) -> bool:
        return False

    def is_enabled(self) -> bool:
        return False

    def set_enabled(self, enabled: bool) -> None:
        raise AutostartError("El inicio automático no está disponible en este sistema")


def create_autostart() -> AutostartStore:
    return WindowsAutostart() if sys.platform == "win32" else NullAutostart()
