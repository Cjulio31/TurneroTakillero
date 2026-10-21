import sys
import types

import pytest

from app.controllers.config_controller import ConfigController
from app.services import autostart as au
from app.services.autostart import (
    MINIMIZED_FLAG,
    AutostartError,
    NullAutostart,
    WindowsAutostart,
    create_autostart,
)
from app.ui.main_window import MainWindow


class FakeRegistry:
    """winreg en memoria: las pruebas nunca tocan el registro real de Windows."""

    HKEY_CURRENT_USER = "HKCU"
    REG_SZ = 1
    KEY_SET_VALUE = 2

    def __init__(self):
        self.values: dict[tuple[str, str], str] = {}
        self.fail = False

    class _Key:
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def OpenKey(self, root, path, *_args):  # noqa: N802
        if self.fail:
            raise PermissionError("denegado")
        return self._Key(path)

    CreateKey = OpenKey  # noqa: N815

    def QueryValueEx(self, key, name):  # noqa: N802
        if (key.path, name) not in self.values:
            raise FileNotFoundError(name)
        return self.values[(key.path, name)], self.REG_SZ

    def SetValueEx(self, key, name, _reserved, _kind, value):  # noqa: N802
        self.values[(key.path, name)] = value

    def DeleteValue(self, key, name):  # noqa: N802
        if (key.path, name) not in self.values:
            raise FileNotFoundError(name)
        del self.values[(key.path, name)]


@pytest.fixture
def registry(monkeypatch):
    fake = FakeRegistry()
    monkeypatch.setitem(
        sys.modules,
        "winreg",
        types.SimpleNamespace(
            **{
                name: getattr(fake, name)
                for name in (
                    "HKEY_CURRENT_USER",
                    "REG_SZ",
                    "KEY_SET_VALUE",
                    "OpenKey",
                    "CreateKey",
                    "QueryValueEx",
                    "SetValueEx",
                    "DeleteValue",
                )
            }
        ),
    )
    monkeypatch.setattr(sys, "platform", "win32")
    return fake


def test_default_command_starts_minimized_in_tray():
    command = au.default_command()
    assert command.endswith(MINIMIZED_FLAG) and MINIMIZED_FLAG == "--minimized"
    assert command.startswith('"')


def test_enable_disable_roundtrip_uses_the_installer_value_name(registry):
    store = WindowsAutostart(command='"C:\\Turnos\\TurnosDesktop.exe" --minimized')
    assert store.is_supported() and not store.is_enabled()
    store.set_enabled(True)
    assert store.is_enabled()
    assert registry.values == {
        (au.RUN_KEY, "TurnosDesktop"): '"C:\\Turnos\\TurnosDesktop.exe" --minimized'
    }
    store.set_enabled(False)
    assert not store.is_enabled() and registry.values == {}
    store.set_enabled(False)  # desactivar lo ya desactivado no falla


def test_registry_errors_become_autostart_error(registry):
    registry.fail = True
    store = WindowsAutostart(command="x")
    assert store.is_enabled() is False  # no se puede leer: se informa como desactivado
    with pytest.raises(AutostartError):
        store.set_enabled(True)


def test_unsupported_platforms(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    store = create_autostart()
    assert isinstance(store, NullAutostart) and not store.is_supported()
    with pytest.raises(AutostartError):
        store.set_enabled(True)
    assert not WindowsAutostart(command="x").is_supported()


class FakeStore:
    def __init__(self, supported=True, enabled=False, fail=False):
        self.supported, self.enabled, self.fail = supported, enabled, fail

    def is_supported(self):
        return self.supported

    def is_enabled(self):
        return self.enabled

    def set_enabled(self, value):
        if self.fail:
            raise AutostartError("sin permisos")
        self.enabled = value


def test_controller_only_writes_when_the_value_changes(ctx):
    store = FakeStore(enabled=True)
    calls = []
    store.set_enabled = lambda value: calls.append(value)
    controller = ConfigController(ctx.config_service, store)
    controller.set_autostart(True)  # ya estaba activo: no escribe
    controller.set_autostart(False)
    assert calls == [False]
    assert ConfigController(ctx.config_service).autostart_supported() is False


def test_configuration_page_applies_the_switch(qtbot, ctx):
    store = FakeStore()
    window = MainWindow(ctx, autostart=store)
    qtbot.addWidget(window)
    page = window.pages["Configuración"]
    assert not page.start_with_windows.isHidden() and not page.start_with_windows.isChecked()
    page.start_with_windows.setChecked(True)
    assert "sin guardar" in page.action_bar.title
    assert page.save() and store.enabled
    page.start_with_windows.setChecked(False)
    assert page.save() and not store.enabled


def test_configuration_page_reports_autostart_failure(qtbot, ctx):
    window = MainWindow(ctx, autostart=FakeStore(fail=True))
    qtbot.addWidget(window)
    page = window.pages["Configuración"]
    page.start_with_windows.setChecked(True)
    assert page.save() is False
    assert "inicio con Windows" in page.action_bar.title
    assert page.action_bar.save_button.isEnabled()  # se puede reintentar


def test_switch_is_hidden_when_autostart_is_not_supported(qtbot, ctx):
    window = MainWindow(ctx, autostart=FakeStore(supported=False))
    qtbot.addWidget(window)
    assert window.pages["Configuración"].start_with_windows.isHidden()
