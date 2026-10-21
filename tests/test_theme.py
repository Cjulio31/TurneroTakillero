import struct

import pytest
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvg import QSvgRenderer

from app.controllers import app_state as st
from app.controllers.config_controller import ConfigController
from app.models.configuration import Configuration
from app.services.health_service import HealthService
from app.ui import icons
from app.ui.main_window import MainWindow
from app.ui.theme import (
    DARK,
    LIGHT,
    PALETTES,
    build_stylesheet,
    state_level,
    theme,
    turn_level,
)
from app.ui.tray import make_icon
from app.ui.widgets import BADGE_ROLE, ActionBar, MessageBanner, Pill, Switch
from app.utils.resources import resource_path


@pytest.fixture(autouse=True)
def restore_light_theme():
    theme.set_mode(LIGHT)
    yield
    theme.set_mode(LIGHT)


def _luminance(color: str) -> float:
    def channel(value: int) -> float:
        v = value / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg: str, bg: str) -> float:
    lighter, darker = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


# --- tema ------------------------------------------------------------------------------------


def test_light_is_the_default_theme():
    assert Configuration().theme == LIGHT
    assert theme.mode == LIGHT


@pytest.mark.parametrize("mode", [LIGHT, DARK])
def test_palettes_meet_wcag_aa_contrast(mode):
    p = PALETTES[mode]
    pairs = [
        (p.text, p.bg),
        (p.text, p.surface),
        (p.text2, p.surface),
        (p.muted, p.surface),
        (p.muted, p.bg),
        (p.accent, p.surface),
        (p.on_accent, p.accent),
        (p.on_accent, p.err),  # insignia del menú
    ]
    for level in ("ok", "warn", "err", "off"):
        pairs.append((p.fg(level), p.bg_of(level)))
    for fg, bg in pairs:
        assert contrast(fg, bg) >= 4.5, f"{mode}: {fg} sobre {bg} = {contrast(fg, bg):.2f}"


def test_set_mode_applies_and_notifies(qtbot):
    seen = []
    theme.changed.connect(seen.append)
    theme.set_mode(DARK)
    assert theme.mode == DARK and theme.palette is PALETTES[DARK]
    assert PALETTES[DARK].accent in build_stylesheet(theme.palette)
    theme.set_mode("no-existe")  # un valor desconocido vuelve al tema claro
    assert theme.mode == LIGHT
    assert seen == [DARK, LIGHT]


def test_state_and_turn_levels():
    assert state_level(st.READY) == "ok" and state_level(st.CONNECTING) == "warn"
    assert state_level(st.UNAVAILABLE) == "err" and state_level(st.DISABLED) == "off"
    assert state_level("???") == "off"
    assert turn_level("COMPLETED") == "ok" and turn_level("ERROR") == "err"
    assert turn_level("RECEIVED") == "off"


def test_theme_value_is_validated():
    with pytest.raises(ValueError):
        ConfigController.validate(Configuration(theme="azul"))
    ConfigController.validate(Configuration(theme="dark"))


def test_toggle_theme_switches_and_persists(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    assert window.theme_button.text() == "Modo oscuro"
    window.toggle_theme()
    assert theme.mode == DARK and ctx.config_service.load().theme == DARK
    assert window.theme_button.text() == "Modo claro"
    window.toggle_theme()
    assert theme.mode == LIGHT and ctx.config_service.load().theme == LIGHT


# --- íconos y recursos -----------------------------------------------------------------------


@pytest.mark.parametrize("name", icons.ICON_NAMES)
def test_every_icon_is_valid_svg(name):
    renderer = QSvgRenderer(QByteArray(icons.svg(name, "#000000").encode()))
    assert renderer.isValid(), name
    assert not icons.pixmap(name, "#112233", 16).isNull()


def test_app_icon_files_exist_and_ico_has_all_sizes():
    assert not icons.app_icon().isNull()
    assert not make_icon("#c0392b").isNull()
    data = resource_path("resources/icons/app.ico").read_bytes()
    _, kind, count = struct.unpack("<HHH", data[:6])
    sizes = [(data[6 + 16 * i] or 256) for i in range(count)]
    assert kind == 1 and sizes == [16, 24, 32, 48, 64, 128, 256]
    assert data[6 + 16 * 6 + 12 : 6 + 16 * 6 + 16]  # la última entrada apunta a un PNG
    png_offset = struct.unpack("<I", data[6 + 16 * 6 + 12 : 6 + 16 * 6 + 16])[0]
    assert data[png_offset : png_offset + 8] == b"\x89PNG\r\n\x1a\n"


# --- widgets ---------------------------------------------------------------------------------


def test_switch_behaves_like_a_checkbox(qtbot):
    switch = Switch("Imprimir")
    qtbot.addWidget(switch)
    switch.show()
    assert not switch.isChecked()
    qtbot.mouseClick(switch, Qt.MouseButton.LeftButton)
    assert switch.isChecked()
    qtbot.mouseClick(switch, Qt.MouseButton.LeftButton)
    assert not switch.isChecked()
    assert switch.sizeHint().width() > Switch.TRACK_W


def test_pill_and_message_banner(qtbot):
    pill = Pill("LISTO", "ok")
    qtbot.addWidget(pill)
    assert pill.text() == "LISTO" and pill.level == "ok"
    pill.set_state("err", "ERROR")
    assert pill.text() == "ERROR" and pill.level == "err"

    banner = MessageBanner()
    qtbot.addWidget(banner)
    assert banner.isHidden() and banner.text() == ""
    banner.set_message("Guardado", "ok")
    assert not banner.isHidden() and banner.text() == "Guardado"
    banner.set_message("", "ok")
    assert banner.isHidden()


def test_action_bar_states(qtbot):
    bar = ActionBar("Se aplican al reconectar.")
    qtbot.addWidget(bar)
    assert not bar.save_button.isEnabled() and "Sin cambios" in bar.title
    bar.set_dirty(True)
    assert bar.save_button.isEnabled() and bar.discard_button.isEnabled()
    assert "sin guardar" in bar.title
    bar.show_result("Guardado", "ok")
    assert bar.title == "Guardado" and not bar.save_button.isEnabled()
    bar.show_result("No guardado", "err")  # tras un error se puede reintentar
    assert bar.save_button.isEnabled()


# --- pantallas -------------------------------------------------------------------------------


def test_dashboard_banner_follows_health_level(qtbot, ctx):
    health = HealthService(ctx.state, ctx.db, ctx.turns)
    window = MainWindow(ctx, health=health)
    qtbot.addWidget(window)
    dash = window.pages["Inicio"]
    for component, status in (
        ("hub", st.READY),
        ("serial", st.CONNECTED),
        ("printer", st.AVAILABLE),
    ):
        ctx.state.set_status(component, status)
    health.start()
    health.stop()
    assert dash._banner._title.text() == "OPERATIVO"
    ctx.state.set_status("printer", st.UNAVAILABLE)
    assert dash._banner._title.text() == "ATENCIÓN"
    assert "Impresora no disponible" in dash._banner._summary.text()
    ctx.state.set_status("printer", st.DISABLED)  # apagada a propósito: no es una falla
    assert dash._banner._title.text() == "OPERATIVO"


def test_dashboard_without_health_service_says_so(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    dash = window.pages["Inicio"]
    assert dash._banner._title.text() == "SIN MONITOREO"
    assert dash._subtitle.text() == "Terminal sin configurar"


def test_dashboard_shows_terminal_and_card_details(qtbot, ctx):
    ctx.config_service.save(Configuration(terminal_id="TERM-001", terminal_name="Caja 1"))
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    dash = window.pages["Inicio"]
    assert dash._subtitle.text() == "Terminal TERM-001 · Caja 1"
    ctx.config_service.save(Configuration(terminal_id="T", serial_port="COM3", print_tickets=False))
    dash.refresh()
    assert dash._indicators["serial"]._detail.text() == "COM3 · 9600"
    assert dash._indicators["printer"]._detail.text() == "Impresión desactivada"


def test_menu_badge_counts_turns_in_error(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    row = list(window._names).index("Turnos")
    assert window.menu.item(row).data(BADGE_ROLE) == 0
    ctx.turns.add("A", "T", 1)
    ctx.turns.update_status("A", "ERROR", "PRINT_ERROR", "sin papel")
    window._refresh_turn_pages()
    assert window.menu.item(row).data(BADGE_ROLE) == 1


def test_tables_show_spanish_status_and_empty_state(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.show()
    turns, history = window.pages["Turnos"], window.pages["Historial"]
    turns.refresh()
    # isHidden (no isVisible): la página Turnos no es la que está en pantalla
    assert not turns.empty.isHidden() and turns.table.isHidden()
    ctx.turns.add("A", "T", 5)
    ctx.turns.update_status("A", "COMPLETED")
    history.refresh()
    assert history.table.item(0, 4).text() == "COMPLETADO"
    assert history._count.text() == "1 resultado(s)"
    history.turn.setValue(9)
    history.refresh()
    assert not history.empty.isHidden()
    history.clear_filters()
    assert history.table.rowCount() == 1 and not history.use_date.isChecked()


def test_history_date_field_only_enabled_when_filtering_by_date(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    page = window.pages["Historial"]
    assert not page.date.isEnabled()
    page.use_date.setChecked(True)
    assert page.date.isEnabled()


def test_configuration_tracks_unsaved_changes(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    page = window.pages["Configuración"]
    assert not page.action_bar.save_button.isEnabled()
    page.terminal_name.setText("Caja 2")
    assert "sin guardar" in page.action_bar.title and page.action_bar.save_button.isEnabled()
    page.load()  # descartar
    assert page.terminal_name.text() == "" and not page.action_bar.save_button.isEnabled()
    page.terminal_name.setText("Caja 2")
    assert page.save()
    assert "guardada" in page.action_bar.title
    assert ctx.config_service.load().terminal_name == "Caja 2"


def test_hardware_tracks_unsaved_changes_and_pills(qtbot, ctx):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    page = window.pages["Hardware"]
    page.refresh_ports()
    assert not page.action_bar.save_button.isEnabled()  # actualizar la lista no es un cambio
    page.transmissions.setValue(3)
    assert page.action_bar.save_button.isEnabled()
    ctx.state.set_status("serial", st.CONNECTED)
    ctx.state.set_status("printer", st.DISABLED)
    assert page.serial_pill.text() == "CONECTADO" and page.serial_pill.level == "ok"
    assert page.printer_pill.text() == "DESACTIVADA" and page.printer_pill.level == "off"
    assert page.printer_type.findData("Windows Printer") >= 0  # el valor guardado no se traduce


def test_about_page_copies_info(qtbot, ctx):
    from PySide6.QtWidgets import QApplication

    window = MainWindow(ctx)
    qtbot.addWidget(window)
    about = window.pages["Acerca de"]
    about.copy_info()
    text = QApplication.clipboard().text()
    assert "Turnos Desktop" in text and "Base de datos:" in text


def test_diagnostics_loads_logs_when_opened(qtbot, ctx, tmp_path, monkeypatch):
    from app.utils import constants

    log = tmp_path / "app.log"
    log.write_text("2026-10-05 INFO prueba de log\n", encoding="utf-8")
    monkeypatch.setattr(constants, "LOG_PATH", log)
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.menu.setCurrentRow(list(window._names).index("Diagnóstico"))
    assert "prueba de log" in window.pages["Diagnóstico"].log_view.toPlainText()
