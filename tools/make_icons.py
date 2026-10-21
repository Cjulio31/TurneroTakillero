"""Genera el ícono de la aplicación (favicon) a partir de un SVG.

Uso:  python tools/make_icons.py

Escribe en resources/icons/:
  app.svg  fuente vectorial
  app.png  256x256 (ventana, bandeja)
  app.ico  16/24/32/48/64/128/256 px (ejecutable, instalador, acceso directo)
"""

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "resources" / "icons"
SIZES = (16, 24, 32, 48, 64, 128, 256)

# Marca de la app: tiquete (con muesca lateral) sobre fondo del color de acento.
SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect width="256" height="256" rx="58" fill="#0B7285"/>
  <g fill="none" stroke="#FFFFFF" stroke-width="12" stroke-linecap="round" stroke-linejoin="round">
    <path transform="translate(36 36) scale(7.3)" stroke-width="1.64"
          d="M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z"/>
    <path d="M98 108h60M98 148h36" stroke-width="13"/>
  </g>
</svg>
"""


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(SVG.encode("utf-8"))).render(painter)
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    """ICO con entradas PNG (válido desde Windows Vista)."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        dim = 0 if size >= 256 else size  # 0 = 256 px
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "app.svg").write_text(SVG, encoding="utf-8")
    pngs = [(size, png_bytes(render(size))) for size in SIZES]
    (OUT / "app.png").write_bytes(dict(pngs)[256])
    (OUT / "app.ico").write_bytes(build_ico(pngs))
    print(f"OK: {OUT} ({', '.join(str(s) for s in SIZES)} px)")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
