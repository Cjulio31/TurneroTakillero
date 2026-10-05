# PyInstaller spec de Turnos Desktop. Se ejecuta con: pyinstaller packaging/turnos_desktop.spec
# Modo onedir: dist/TurnosDesktop/TurnosDesktop.exe (arranca más rápido que onefile, no se
# descomprime en %TEMP% en cada inicio y da menos falsos positivos de antivirus).
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = ROOT / "resources" / "icons" / "app.ico"

# keyring y pyserial cargan backends por nombre: PyInstaller no los detecta solo.
hidden = ["keyring.backends.fail", "keyring.backends.null"]
if sys.platform == "win32":
    hidden += [
        "keyring.backends.Windows",
        "win32ctypes.core",
        "serial.tools.list_ports_windows",
    ]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "resources"), "resources")],
    hiddenimports=hidden,
    excludes=["tkinter", "pytest", "pytestqt"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="TurnosDesktop",
    console=False,  # aplicación de bandeja: sin ventana de consola
    icon=str(ICON) if ICON.exists() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="TurnosDesktop")
