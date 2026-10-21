"""Sistema de diseño: paletas clara/oscura, hoja de estilos (QSS) y gestor de tema.

Una sola fuente de colores: ningún widget define hex propios. Los estados se expresan con un
nivel (`ok`, `warn`, `err`, `off`) que cada paleta traduce a color de texto, fondo y borde.
"""

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from string import Template

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from app.controllers import app_state as st
from app.utils import constants

log = logging.getLogger(__name__)

LIGHT = "light"
DARK = "dark"
THEMES = (LIGHT, DARK)
DEFAULT_THEME = LIGHT

LEVELS = ("ok", "warn", "err", "off")
SANS_FAMILIES = ("Segoe UI", "Helvetica Neue", "Arial")
MONO_CSS = '"Cascadia Mono", "Consolas", "Courier New", monospace'


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def blend(fg: str, bg: str, alpha: float) -> str:
    """Mezcla `fg` sobre `bg` (equivale a un `rgba` sin transparencia real, válido en QSS y QColor)."""
    r, g, b = (round(f * alpha + k * (1 - alpha)) for f, k in zip(_rgb(fg), _rgb(bg), strict=True))
    return f"#{r:02X}{g:02X}{b:02X}"


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    side: str
    surface: str
    surface2: str
    border: str
    field_bg: str
    field_border: str
    text: str
    text2: str
    muted: str
    accent: str
    accent_hover: str
    accent_soft: str
    on_accent: str
    log_bg: str
    scrim: str
    ok: str
    ok_bg: str
    ok_border: str
    warn: str
    warn_bg: str
    warn_border: str
    err: str
    err_bg: str
    err_border: str
    err_card: str
    off: str
    off_bg: str
    off_border: str

    def fg(self, level: str) -> str:
        return getattr(self, level if level in LEVELS else "off")

    def bg_of(self, level: str) -> str:
        return getattr(self, f"{level if level in LEVELS else 'off'}_bg")

    def border_of(self, level: str) -> str:
        return getattr(self, f"{level if level in LEVELS else 'off'}_border")


def _make(
    name: str,
    *,
    bg: str,
    side: str,
    surface: str,
    surface2: str,
    border: str,
    field_bg: str,
    field_border: str,
    text: str,
    text2: str,
    muted: str,
    accent: str,
    on_accent: str,
    log_bg: str,
    scrim: str,
    levels: dict[str, tuple[str, str]],
    tint_alpha: float,
    hover_toward: str,
) -> Palette:
    parts: dict[str, str] = {}
    for level, (fg, tint) in levels.items():
        parts[level] = fg
        parts[f"{level}_bg"] = blend(tint, bg, tint_alpha)
        parts[f"{level}_border"] = blend(tint, bg, 0.35)
    return Palette(
        name=name,
        bg=bg,
        side=side,
        surface=surface,
        surface2=surface2,
        border=border,
        field_bg=field_bg,
        field_border=field_border,
        text=text,
        text2=text2,
        muted=muted,
        accent=accent,
        accent_hover=blend(hover_toward, accent, 0.14),
        accent_soft=blend(accent, side, 0.14),
        on_accent=on_accent,
        log_bg=log_bg,
        scrim=scrim,
        err_card=blend(levels["err"][1], surface, 0.06),
        **parts,
    )


PALETTES: dict[str, Palette] = {
    LIGHT: _make(
        LIGHT,
        bg="#F4F6F9",
        side="#FFFFFF",
        surface="#FFFFFF",
        surface2="#EEF2F6",
        border="#E1E6ED",
        field_bg="#FFFFFF",
        field_border="#C7D0DB",
        text="#131A22",
        text2="#3B4A5A",
        muted="#5B6B7C",
        accent="#0B7285",
        on_accent="#FFFFFF",
        log_bg="#F8FAFC",
        scrim="#0A0F14",
        levels={
            "ok": ("#12703F", "#1FA25A"),
            "warn": ("#8A5A00", "#E0A100"),
            "err": ("#B3261E", "#D93B30"),
            "off": ("#4A5868", "#6B7C8F"),
        },
        tint_alpha=0.14,
        hover_toward="#000000",
    ),
    DARK: _make(
        DARK,
        bg="#0E1319",
        side="#121820",
        surface="#151C24",
        surface2="#1B2430",
        border="#1F2A36",
        field_bg="#0E1319",
        field_border="#2B3947",
        text="#E8EEF4",
        text2="#A9B6C4",
        muted="#8FA0B2",
        accent="#4DD0E1",
        on_accent="#0E1319",
        log_bg="#0A0F14",
        scrim="#05080C",
        levels={
            "ok": ("#3DDC97", "#3DDC97"),
            "warn": ("#F5B942", "#F5B942"),
            "err": ("#FF7A6B", "#FF7A6B"),
            "off": ("#B7C3D0", "#8FA0B2"),
        },
        tint_alpha=0.12,
        hover_toward="#FFFFFF",
    ),
}

# --- estados -> nivel -----------------------------------------------------------------------

_STATE_LEVEL = {
    st.CONNECTED: "ok",
    st.READY: "ok",
    st.AVAILABLE: "ok",
    st.OK: "ok",
    st.CONNECTING: "warn",
    st.DISCONNECTED: "err",
    st.UNAVAILABLE: "err",
    st.ERROR: "err",
    st.DISABLED: "off",
    st.UNKNOWN: "off",
}
_TURN_LEVEL = {
    constants.STATUS_COMPLETED: "ok",
    constants.STATUS_PRINTED: "ok",
    constants.STATUS_ERROR: "err",
    constants.STATUS_PROCESSING: "warn",
    constants.STATUS_SENT: "warn",
    constants.STATUS_RECEIVED: "off",
}
LEVEL_ICON = {"ok": "check", "warn": "alert", "err": "xcircle", "off": "minus"}

TURN_STATUS_TEXT = {
    constants.STATUS_RECEIVED: "RECIBIDO",
    constants.STATUS_PROCESSING: "PROCESANDO",
    constants.STATUS_SENT: "ENVIADO",
    constants.STATUS_PRINTED: "IMPRESO",
    constants.STATUS_COMPLETED: "COMPLETADO",
    constants.STATUS_ERROR: "ERROR",
}


def state_level(status: str) -> str:
    """Nivel visual de un estado de componente (hub, serial, impresora, base de datos)."""
    return _STATE_LEVEL.get(status, "off")


def turn_level(status: str) -> str:
    """Nivel visual del estado de un turno."""
    return _TURN_LEVEL.get(status, "off")


# --- hoja de estilos -------------------------------------------------------------------------

_QSS = Template(
    """
QMainWindow, QDialog { background: $bg; }
QMessageBox { background: $surface; }
QWidget { color: $text; }
QWidget#Page { background: $bg; }
QScrollArea#PageScroll { background: $bg; border: none; }

QToolTip { background: $surface; color: $text; border: 1px solid $border; padding: 6px 8px; }

/* barra lateral */
QFrame#Sidebar { background: $side; border-right: 1px solid $border; }
QFrame#BrandMark { background: $accent_soft; border-radius: 12px; }
QLabel#BrandTitle { font-size: 17px; font-weight: 800; }
QLabel#BrandSub { color: $muted; font-size: 12px; }
QLabel#SidebarVersion { color: $muted; font-size: 12px; }
QListWidget#Nav { background: transparent; border: none; outline: 0; font-size: 14px; selection-color: $accent; selection-background-color: transparent; }
QListWidget#Nav::item { padding: 11px 12px; margin: 2px 0; border-radius: 12px; color: $text2; font-weight: 600; }
QListWidget#Nav::item:hover { background: $surface2; }
QListWidget#Nav::item:selected { background: $accent_soft; color: $accent; font-weight: 700; }
QPushButton#ThemeToggle { border: none; background: transparent; color: $muted; padding: 6px 8px; font-size: 12px; font-weight: 600; }
QPushButton#ThemeToggle:hover { background: $surface2; color: $text; }

/* textos */
QLabel#PageTitle { font-size: 28px; font-weight: 800; }
QLabel#PageSubtitle { color: $muted; font-size: 14px; }
QLabel#CardCaption { color: $muted; font-size: 11px; font-weight: 700; }
QLabel#FieldCaption { color: $muted; font-size: 11px; font-weight: 700; }
QLabel#Hint { color: $muted; font-size: 13px; }
QLabel#EmptyState { color: $muted; font-size: 15px; padding: 36px; }
QLabel[mono="true"] { font-family: $mono; }

/* tarjetas */
QFrame#Card { background: $surface; border: 1px solid $border; border-radius: 18px; }
QFrame#Highlight { background: $accent_soft; border-radius: 14px; }
QFrame#Dashed { background: $field_bg; border: 1px dashed $field_border; border-radius: 12px; }
QFrame#IconBox { background: $surface2; border-radius: 11px; }
QGroupBox { background: $surface; border: 1px solid $border; border-radius: 18px; margin-top: 12px; padding: 26px 20px 18px 20px; font-weight: 800; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 18px; padding: 0 8px; color: $muted; font-size: 12px; }

/* botones */
QPushButton { background: transparent; border: 1px solid $field_border; border-radius: 12px; padding: 9px 20px; font-weight: 600; min-height: 22px; }
QPushButton:hover { background: $surface2; }
QPushButton:pressed { background: $border; }
QPushButton:focus { border-color: $accent; }
QPushButton:disabled { color: $muted; border-color: $border; background: transparent; }
QPushButton[primary="true"] { background: $accent; color: $on_accent; border: 1px solid $accent; font-weight: 800; }
QPushButton[primary="true"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[primary="true"]:disabled { background: $border; color: $muted; border-color: $border; }
QPushButton[danger="true"] { color: $err; border-color: $err_border; }
QPushButton[danger="true"]:hover { background: $err_bg; }
QPushButton[tool="true"] { text-align: left; padding: 12px 16px; background: $surface; border-color: $field_border; }
QPushButton[tool="true"]:hover { background: $surface2; }
QPushButton[tool="true"][danger="true"] { background: transparent; }

/* campos */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QPlainTextEdit { background: $field_bg; border: 1px solid $field_border; border-radius: 12px; padding: 8px 12px; min-height: 22px; selection-background-color: $accent; selection-color: $on_accent; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus { border: 1px solid $accent; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled, QDateEdit:disabled { color: $muted; background: $surface2; }
QSpinBox, QDoubleSpinBox { padding-right: 30px; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 26px; border: none; background: transparent; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 26px; border: none; background: transparent; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: $surface2; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url($chevron_up); width: 10px; height: 10px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url($chevron); width: 10px; height: 10px; }
QComboBox::drop-down, QDateEdit::drop-down { border: none; width: 30px; }
QComboBox::down-arrow, QDateEdit::down-arrow { image: url($chevron); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: $surface; border: 1px solid $border; selection-background-color: $accent_soft; selection-color: $accent; outline: 0; padding: 4px; }
QPlainTextEdit#LogView { background: $log_bg; border: 1px solid $border; border-radius: 14px; padding: 12px 14px; font-family: $mono; font-size: 12px; color: $text2; }

/* tablas */
QTableWidget, QTableView { background: $surface; border: 1px solid $border; border-radius: 16px; gridline-color: transparent; outline: 0; selection-background-color: $accent_soft; selection-color: $text; }
QTableView::item { padding: 0 10px; border-bottom: 1px solid $border; }
QTableView::item:selected { background: $accent_soft; color: $text; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section { background: $surface2; color: $muted; border: none; padding: 12px 10px; font-weight: 700; font-size: 11px; }
QHeaderView::section:first { border-top-left-radius: 15px; }
QHeaderView::section:last { border-top-right-radius: 15px; }
QTableCornerButton::section { background: $surface2; border: none; }

/* menús y barras */
QMenu { background: $surface; border: 1px solid $border; padding: 6px; }
QMenu::item { padding: 8px 18px; border-radius: 8px; }
QMenu::item:selected { background: $accent_soft; color: $accent; }
QMenu::item:disabled { color: $muted; }
QMenu::separator { height: 1px; background: $border; margin: 6px 8px; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: $field_border; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: $field_border; border-radius: 4px; min-width: 28px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""
)


def build_stylesheet(p: Palette, arrows: dict[str, str] | None = None) -> str:
    values = {"chevron": "", "chevron_up": "", **(arrows or {})}
    return _QSS.safe_substitute({**p.__dict__, "mono": MONO_CSS, **values})


def build_qpalette(p: Palette) -> QPalette:
    qp = QPalette()
    roles = {
        QPalette.ColorRole.Window: p.bg,
        QPalette.ColorRole.WindowText: p.text,
        QPalette.ColorRole.Base: p.field_bg,
        QPalette.ColorRole.AlternateBase: p.surface2,
        QPalette.ColorRole.Text: p.text,
        QPalette.ColorRole.Button: p.surface,
        QPalette.ColorRole.ButtonText: p.text,
        QPalette.ColorRole.ToolTipBase: p.surface,
        QPalette.ColorRole.ToolTipText: p.text,
        QPalette.ColorRole.Highlight: p.accent,
        QPalette.ColorRole.HighlightedText: p.on_accent,
        QPalette.ColorRole.PlaceholderText: p.muted,
        QPalette.ColorRole.Link: p.accent,
    }
    for role, color in roles.items():
        qp.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        qp.setColor(QPalette.ColorGroup.Disabled, role, QColor(p.muted))
    return qp


def _arrow_paths(p: Palette) -> dict[str, str]:
    """Flechas de desplegables y spin: QSS solo acepta imágenes por archivo, no en memoria."""
    from app.ui import icons

    folder = Path(tempfile.gettempdir()) / "turnos_desktop_theme"
    paths: dict[str, str] = {}
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for key, icon_name in (("chevron", "chevron"), ("chevron_up", "chevron-up")):
            path = folder / f"{key}_{p.name}.png"
            icons.pixmap(icon_name, p.muted, 14, 2.0, dpr=2).save(str(path), "PNG")
            paths[key] = path.as_posix()
    except OSError as exc:
        log.warning("No se pudieron escribir las flechas de los desplegables: %s", exc)
    return paths


class ThemeManager(QObject):
    """Tema vigente (claro por defecto). `changed` avisa a los widgets que dibujan por su cuenta."""

    changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._mode = DEFAULT_THEME
        self._applied: str | None = None  # tema que ya está aplicado a la QApplication

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def palette(self) -> Palette:
        return PALETTES[self._mode]

    def set_mode(self, mode: str, app: QApplication | None = None) -> None:
        """Cambia el tema y lo aplica a la aplicación. Un valor desconocido vuelve al claro.

        Si el tema ya estaba aplicado no hace nada: reaplicar la hoja de estilos vuelve a pulir
        todos los widgets vivos y es caro.
        """
        mode = mode if mode in PALETTES else DEFAULT_THEME
        app = app or QApplication.instance()
        if mode == self._mode and (app is None or self._applied == mode):
            return
        self._mode = mode
        if app is not None:
            self.apply(app)
        self.changed.emit(self._mode)

    def apply(self, app: QApplication) -> None:
        self._applied = self._mode
        p = self.palette
        app.setStyle("Fusion")
        font = QFont()
        font.setFamilies(list(SANS_FAMILIES))
        font.setPointSize(10)
        app.setFont(font)
        app.setPalette(build_qpalette(p))
        app.setStyleSheet(build_stylesheet(p, _arrow_paths(p)))


theme = ThemeManager()
