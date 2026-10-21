import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Ruta de un recurso (`resources/...`): junto al código, o dentro del bundle empaquetado."""
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        root = Path(__file__).resolve().parents[2]
    return root / relative
