"""Widgets reutilizables del sistema de diseño. Solo presentación: ninguna lógica de negocio."""

from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui import icons
from app.ui.theme import LEVEL_ICON, LIGHT, theme, turn_level
from app.utils import constants

BADGE_ROLE = Qt.ItemDataRole.UserRole + 1  # contador que la barra lateral dibuja como insignia
STATUS_ROLE = Qt.ItemDataRole.UserRole  # estado crudo del turno (el texto visible va en español)


# --- helpers de página ----------------------------------------------------------------------


def mono_font(pixel_size: int, bold: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(["Cascadia Mono", "Consolas", "Courier New"])
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(pixel_size)
    font.setBold(bold)
    return font


def header_row(title: str, subtitle: str = "") -> tuple[QHBoxLayout, QLabel]:
    """Cabecera de página: título y subtítulo a la izquierda; el llamador suma lo de la derecha."""
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    column = QVBoxLayout()
    column.setSpacing(2)
    column.addWidget(title_label)
    column.addWidget(subtitle_label)
    row = QHBoxLayout()
    row.addLayout(column)
    row.addStretch(1)
    return row, subtitle_label


class _IconBinder(QObject):
    """Mantiene el ícono de un botón con el color del tema vigente."""

    def __init__(self, button: QAbstractButton, name: str, color_attr: str, size: int):
        super().__init__(button)
        self._button, self._name, self._attr, self._size = button, name, color_attr, size
        theme.changed.connect(self.apply)
        self.apply()

    def apply(self, *_: object) -> None:
        self._button.setIcon(
            icons.icon(self._name, getattr(theme.palette, self._attr), size=self._size)
        )
        self._button.setIconSize(QSize(self._size, self._size))


def bind_icon(button: QAbstractButton, name: str, color_attr: str = "text", size: int = 18) -> None:
    """Pone un ícono SVG al botón y lo recolorea al cambiar de tema."""
    _IconBinder(button, name, color_attr, size)


# --- piezas de formulario -------------------------------------------------------------------


def caption(text: str, object_name: str = "FieldCaption") -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName(object_name)
    return label


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    return label


def field(caption_text: str, widget: QWidget) -> QWidget:
    """Campo con su rótulo encima (los rótulos de QFormLayout van al costado)."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(caption(caption_text))
    layout.addWidget(widget)
    return box


def card(object_name: str = "Card") -> QFrame:
    frame = QFrame()
    frame.setObjectName(object_name)
    return frame


def card_header(icon_name: str, title: str, pill: QWidget | None = None) -> QHBoxLayout:
    """Cabecera de una tarjeta: ícono + título a la izquierda, estado (píldora) a la derecha."""
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(IconBox(icon_name))
    row.addWidget(caption(title, "CardCaption"))
    row.addStretch(1)
    if pill is not None:
        row.addWidget(pill)
    return row


def connect_changes(widget: QWidget, callback: Callable[[], None]) -> None:
    """Llama a `callback` cuando el usuario cambia el valor de un campo."""
    if isinstance(widget, QLineEdit):
        widget.textChanged.connect(lambda *_: callback())
    elif isinstance(widget, QSpinBox):
        widget.valueChanged.connect(lambda *_: callback())
    elif isinstance(widget, QComboBox):
        widget.currentIndexChanged.connect(lambda *_: callback())
        if widget.isEditable():
            widget.editTextChanged.connect(lambda *_: callback())
    elif isinstance(widget, QCheckBox):
        widget.toggled.connect(lambda *_: callback())


# --- interruptor ----------------------------------------------------------------------------


class Switch(QCheckBox):
    """Interruptor deslizante. Se usa y se prueba como un QCheckBox (isChecked/setChecked)."""

    TRACK_W, TRACK_H = 44, 26

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        metrics = self.fontMetrics()
        extra = 10 + metrics.horizontalAdvance(self.text()) if self.text() else 0
        return QSize(self.TRACK_W + extra, max(self.TRACK_H, metrics.height()))

    def hitButton(self, pos) -> bool:  # toda el área es clicable, también el texto
        return self.rect().contains(pos)

    def paintEvent(self, _event) -> None:
        p = theme.palette
        on, enabled = self.isChecked(), self.isEnabled()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, (self.height() - self.TRACK_H) / 2, self.TRACK_W, self.TRACK_H)
        track_color = QColor(p.accent if on else p.field_border)
        knob_color = QColor(p.on_accent if on else (p.surface if p.name == LIGHT else p.muted))
        if not enabled:
            track_color.setAlphaF(0.45)
            knob_color.setAlphaF(0.6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, self.TRACK_H / 2, self.TRACK_H / 2)
        d = self.TRACK_H - 8
        x = track.right() - 4 - d if on else track.left() + 4
        painter.setBrush(knob_color)
        painter.drawEllipse(QRectF(x, track.top() + 4, d, d))
        if self.hasFocus():
            painter.setPen(QPen(QColor(p.accent), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(track.adjusted(-2, -2, 2, 2), 15, 15)
        if self.text():
            painter.setPen(QColor(p.text if enabled else p.muted))
            text_rect = QRectF(
                self.TRACK_W + 10, 0, self.width() - self.TRACK_W - 10, self.height()
            )
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                self.text(),
            )


# --- píldoras e íconos ----------------------------------------------------------------------


class Pill(QFrame):
    """Etiqueta redondeada de estado: glifo + texto, coloreada por nivel (ok/warn/err/off)."""

    def __init__(self, text: str = "", level: str = "off", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Pill")
        self._level = level
        self._icon = QLabel()
        self._label = QLabel(text)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 12, 4)
        layout.setSpacing(6)
        layout.addWidget(self._icon)
        layout.addWidget(self._label)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        theme.changed.connect(self._refresh)
        self._refresh()

    def set_state(self, level: str, text: str) -> None:
        self._level = level
        self._label.setText(text)
        self._refresh()

    def text(self) -> str:
        return self._label.text()

    @property
    def level(self) -> str:
        return self._level

    def _refresh(self, *_: object) -> None:
        p = theme.palette
        fg = p.fg(self._level)
        self.setStyleSheet(
            # `border: none` haría que Qt ignore el radio: se usa un borde del mismo color.
            f"QFrame#Pill {{ background: {p.bg_of(self._level)}; "
            f"border: 1px solid {p.bg_of(self._level)}; border-radius: 13px; }}"
        )
        self._label.setStyleSheet(
            f"color: {fg}; font-weight: 800; font-size: 12px; background: transparent;"
        )
        self._icon.setStyleSheet("background: transparent;")
        self._icon.setPixmap(icons.pixmap(LEVEL_ICON.get(self._level, "minus"), fg, 13, 3.0))


class IconBox(QFrame):
    """Cuadrado con esquinas redondeadas que aloja un ícono (cabecera de tarjetas)."""

    def __init__(self, name: str, size: int = 38, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("IconBox")
        self._name = name
        self._level = "off"
        self._glyph = 20 if size >= 36 else 18
        self.setFixedSize(size, size)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setGeometry(0, 0, size, size)
        theme.changed.connect(self._refresh)
        self._refresh()

    def set_level(self, level: str) -> None:
        self._level = level
        self._refresh()

    def _refresh(self, *_: object) -> None:
        p = theme.palette
        err = self._level == "err"
        self.setStyleSheet(
            f"QFrame#IconBox {{ background: {p.err_bg if err else p.surface2}; "
            "border-radius: 11px; }"
        )
        self._label.setStyleSheet("background: transparent;")
        self._label.setPixmap(icons.pixmap(self._name, p.err if err else p.text2, self._glyph))


class MessageBanner(QFrame):
    """Mensaje de resultado (éxito/aviso/error). Se oculta solo cuando no hay texto."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("MessageBanner")
        self._level = "off"
        self._icon = QLabel()
        self._label = QLabel()
        self._label.setWordWrap(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._label, 1)
        theme.changed.connect(self._refresh)
        self.setVisible(False)
        self._refresh()

    def set_message(self, text: str, level: str = "off") -> None:
        self._level = level
        self._label.setText(text)
        self.setVisible(bool(text))
        self._refresh()

    def setText(self, text: str) -> None:  # compatibilidad con QLabel
        self.set_message(text, self._level)

    def text(self) -> str:
        return self._label.text()

    def _refresh(self, *_: object) -> None:
        p = theme.palette
        fg = p.fg(self._level)
        self.setStyleSheet(
            f"QFrame#MessageBanner {{ background: {p.bg_of(self._level)}; "
            f"border: 1px solid {p.border_of(self._level)}; border-radius: 12px; }}"
        )
        self._label.setStyleSheet(
            f"color: {fg}; font-weight: 700; font-size: 14px; background: transparent;"
        )
        self._icon.setStyleSheet("background: transparent;")
        self._icon.setPixmap(icons.pixmap(LEVEL_ICON.get(self._level, "info"), fg, 18, 2.4))


class ActionBar(QFrame):
    """Barra inferior de formularios: estado de cambios + Descartar/Guardar."""

    def __init__(self, hint_text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._hint = hint_text
        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._title = QLabel()
        self._subtitle = QLabel()
        self._subtitle.setObjectName("Hint")
        self.discard_button = QPushButton("Descartar")
        self.save_button = QPushButton("Guardar")
        self.save_button.setProperty("primary", True)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(self._title)
        text.addWidget(self._subtitle)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(14)
        layout.addWidget(self._dot)
        layout.addLayout(text, 1)
        layout.addWidget(self.discard_button)
        layout.addWidget(self.save_button)
        self._level = "off"
        self._text = ""
        self._sub = ""
        theme.changed.connect(self._refresh)
        self.set_dirty(False)

    def set_dirty(self, dirty: bool) -> None:
        if dirty:
            self._show("warn", "Hay cambios sin guardar", self._hint)
        else:
            self._show("off", "Sin cambios pendientes", "")
        self.discard_button.setEnabled(dirty)
        self.save_button.setEnabled(dirty)

    def show_result(self, text: str, level: str) -> None:
        """Resultado de guardar. Tras un error se puede corregir y volver a intentar."""
        self._show(level, text, "")
        self.discard_button.setEnabled(level == "err")
        self.save_button.setEnabled(level == "err")

    @property
    def title(self) -> str:
        return self._text

    def _show(self, level: str, text: str, sub: str) -> None:
        self._level, self._text, self._sub = level, text, sub
        self._refresh()

    def _refresh(self, *_: object) -> None:
        p = theme.palette
        self._dot.setStyleSheet(f"background: {p.fg(self._level)}; border-radius: 5px;")
        self._title.setText(self._text)
        self._title.setStyleSheet(
            "font-size: 14px; font-weight: 700; "
            f"color: {p.fg(self._level) if self._level != 'off' else p.text};"
        )
        self._subtitle.setText(self._sub)
        self._subtitle.setVisible(bool(self._sub))


# --- tablas ---------------------------------------------------------------------------------


def style_cell(
    item: QTableWidgetItem,
    *,
    mono: int = 0,
    bold: bool = False,
    muted: bool = False,
    status: str = "",
) -> None:
    """Fuente, color y fondo de una celda con el tema vigente (las filas en ERROR se tiñen)."""
    p = theme.palette
    if mono:
        item.setFont(mono_font(mono, bold))
    item.setForeground(QBrush(QColor(p.muted if muted else p.text)))
    item.setBackground(QBrush(QColor(p.err_bg)) if status == constants.STATUS_ERROR else QBrush())


def retint_table(table: QTableWidget, cell_styles: dict[int, dict]) -> None:
    """Recolorea la tabla al cambiar de tema sin volver a consultar los datos."""
    for row in range(table.rowCount()):
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item is not None:
                style_cell(item, status=item.data(STATUS_ROLE) or "", **cell_styles.get(col, {}))
    table.viewport().update()


def style_table(table: QTableWidget, headers: Sequence[str], widths: Sequence[int | None]) -> None:
    """Estilo común de tablas. `widths`: píxeles por columna; None = ocupa el espacio sobrante."""
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels([h.upper() for h in headers])
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setShowGrid(False)
    table.setAlternatingRowColors(False)
    table.setWordWrap(False)  # una línea por fila: el texto largo se corta con "…"
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(48)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setStretchLastSection(False)
    for col, width in enumerate(widths):
        if width is None:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col, width)


class PillDelegate(QStyledItemDelegate):
    """Dibuja el estado de un turno como píldora. El valor crudo va en STATUS_ROLE."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        if not text:
            return
        level = turn_level(index.data(STATUS_ROLE) or "")
        p = theme.palette
        font = QFont(opt.font)  # la misma fuente para medir y para dibujar
        font.setBold(True)
        font.setPixelSize(max(10, QFontMetrics(opt.font).height() - 3))
        metrics = QFontMetrics(font)
        height = metrics.height() + 12
        glyph = 12
        width = metrics.horizontalAdvance(text) + glyph + 34
        rect = QRect(opt.rect.left() + 8, opt.rect.center().y() - height // 2, width, height)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(p.bg_of(level))))
        painter.drawRoundedRect(rect, height / 2, height / 2)
        pix = icons.pixmap(LEVEL_ICON[level], p.fg(level), glyph, 3.0)
        painter.drawPixmap(rect.left() + 10, rect.center().y() - glyph // 2 + 1, pix)
        painter.setFont(font)
        painter.setPen(QColor(p.fg(level)))
        text_rect = rect.adjusted(10 + glyph + 6, 0, 0, 0)
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter), text)
        painter.restore()


class NavDelegate(QStyledItemDelegate):
    """Menú lateral: dibuja una insignia con el contador de BADGE_ROLE (p. ej. turnos en error)."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        super().paint(painter, option, index)
        count = index.data(BADGE_ROLE)
        if not count:
            return
        p = theme.palette
        text = str(count) if count < 100 else "99+"
        metrics = QFontMetrics(option.font)
        width = max(22, metrics.horizontalAdvance(text) + 14)
        rect = QRect(option.rect.right() - width - 12, option.rect.center().y() - 11, width, 22)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p.err))
        painter.drawRoundedRect(rect, 11, 11)
        font = option.font
        font.setBold(True)
        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(QColor(p.on_accent if p.name != LIGHT else "#FFFFFF"))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
        painter.restore()
