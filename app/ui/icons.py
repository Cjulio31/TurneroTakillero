"""Íconos de la interfaz: trazos SVG (estilo lineal) dibujados con el color del tema."""

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.utils.resources import resource_path

_BODIES: dict[str, str] = {
    "home": '<path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "sliders": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    "chip": (
        '<rect x="5" y="5" width="14" height="14" rx="2"/>'
        '<path d="M9 9h6v6H9zM9 1v4M15 1v4M9 19v4M15 19v4M19 9h4M19 15h4M1 9h4M1 15h4"/>'
    ),
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
    "ticket": (
        '<path d="M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1'
        '-2-2v-2a2 2 0 0 0 0-4z"/>'
    ),
    "zap": '<path d="M13 2L3 14h9l-1 8 10-12h-9z"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "alert": (
        '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 '
        '0-3.42 0zM12 9v4M12 17h.01"/>'
    ),
    "xcircle": '<circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/>',
    "minus": '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
    "globe": (
        '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 '
        '0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
    ),
    "plug": '<path d="M3 9h5v6H3zM16 9h5v6h-5zM8 12h8"/>',
    "printer": (
        '<path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1'
        '-2 2h-2M6 14h12v8H6z"/>'
    ),
    "database": (
        '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3M3 5v14c'
        '0 1.66 4 3 9 3s9-1.34 9-3V5"/>'
    ),
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h8"/>',
    "trash": (
        '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 '
        '0 1-2-2L5 6"/>'
    ),
    "send": '<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>',
    "refresh": '<path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.5 9A9 9 0 0 0 5.6 5.6L1 10M23 14l-4.6 4.4A9 9 0 0 1 3.5 15"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "eye": '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": (
        '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 '
        "4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24"
        '-4.24M1 1l22 22"/>'
    ),
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    "sun": (
        '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 '
        '12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
    ),
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "chevron": '<path d="M6 9l6 6 6-6"/>',
    "chevron-up": '<path d="M18 15l-6-6-6 6"/>',
    "power": '<path d="M18.36 6.64a9 9 0 1 1-12.73 0M12 2v10"/>',
}

ICON_NAMES = tuple(_BODIES)


def svg(name: str, color: str, stroke: float = 1.8) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
        f"{_BODIES[name]}</svg>"
    )


@lru_cache(maxsize=1024)
def pixmap(name: str, color: str, size: int = 20, stroke: float = 1.8, dpr: int = 2) -> QPixmap:
    """Ícono dibujado a `size` px lógicos (con `dpr` veces más píxeles para pantallas nítidas)."""
    px = QPixmap(size * dpr, size * dpr)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg(name, color, stroke).encode("utf-8"))).render(painter)
    painter.end()
    px.setDevicePixelRatio(dpr)
    return px


def app_icon() -> QIcon:
    """Ícono de la aplicación (ventana, bandeja). Vacío si el recurso no está disponible."""
    path = resource_path("resources/icons/app.png")
    return QIcon(str(path)) if path.exists() else QIcon()


def icon(name: str, color: str, selected: str | None = None, size: int = 20) -> QIcon:
    """QIcon con un color normal y, opcionalmente, otro para el modo seleccionado/activo."""
    result = QIcon()
    normal = pixmap(name, color, size)
    result.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(normal, QIcon.Mode.Disabled, QIcon.State.Off)
    if selected:
        active = pixmap(name, selected, size)
        for mode in (QIcon.Mode.Selected, QIcon.Mode.Active):
            result.addPixmap(active, mode, QIcon.State.Off)
    return result
