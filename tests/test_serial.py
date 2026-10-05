import pytest
import serial
from PySide6.QtCore import QThreadPool

from app.communication.backoff import BackoffPolicy
from app.controllers import app_state as st
from app.controllers.diagnostics_controller import DiagnosticsController
from app.hardware.serial_device import SerialDevice, SerialSettings
from app.protocol.turn_protocol import TurnProtocol
from app.services.errors import SerialSendError, SerialUnavailableError
from app.services.serial_service import SerialService
from app.services.turn_service import TurnService

PACKET_25 = bytes([0x99, 0x55, 0x19])


def test_protocol_packet_and_format():
    p = TurnProtocol()
    assert p.build_packet(25) == PACKET_25
    assert p.build_packet(1) == b"\x99\x55\x01"
    assert p.build_packet(255) == b"\x99\x55\xff"
    assert p.format_packet(PACKET_25) == "99 55 19"
    for bad in (0, 256, -1, "25", None, True, 2.5):
        with pytest.raises(ValueError):
            p.build_packet(bad)


class FakeDevice:
    def __init__(self, fail_on_write: int | None = None):
        self.writes: list[bytes] = []
        self.fail_on_write = fail_on_write
        self.is_open = True

    def write(self, data):
        if self.fail_on_write is not None and len(self.writes) + 1 == self.fail_on_write:
            raise serial.SerialException("dispositivo desconectado")
        self.writes.append(data)
        return len(data)

    def close(self):
        self.is_open = False


class Env:
    def __init__(self, ctx, port="loop://", factory=None, listed=None, transmissions=2):
        self.settings = SerialSettings(port=port, transmissions=transmissions)
        self.listed = listed if listed is not None else []
        self.devices: list = []
        self.factory_error: Exception | None = None
        self._factory = factory
        self.service = SerialService(
            ctx.state,
            ctx.events,
            settings_provider=lambda: self.settings,
            device_factory=self._make,
            port_lister=lambda: list(self.listed),
            backoff=BackoffPolicy([0.01, 0.02]),
            health_interval_ms=20,
        )
        self.ctx = ctx

    def _make(self, settings):
        if self.factory_error:
            raise self.factory_error
        device = self._factory() if self._factory else SerialDevice.open(settings)
        self.devices.append(device)
        return device


@pytest.fixture
def make_env(qtbot, ctx):
    created = []

    def factory(**kwargs):
        env = Env(ctx, **kwargs)
        created.append(env)
        return env

    yield factory
    for env in created:
        env.service.stop()
    QThreadPool.globalInstance().waitForDone()


def test_sends_packet_twice_over_loopback(make_env, ctx):
    env = make_env()
    assert env.service.connect()
    assert ctx.state.status("serial") == st.CONNECTED
    env.service.send_turn(25)
    assert env.devices[0].read(6) == PACKET_25 * 2
    assert ctx.events.recent()[0]["event_type"] == "SERIAL_CONNECTED"


def test_transmissions_are_configurable(make_env):
    env = make_env(factory=FakeDevice, transmissions=3)
    env.service.connect()
    env.service.send_turn(25)
    assert env.devices[0].writes == [PACKET_25] * 3


def test_send_without_connection_raises_unavailable(make_env):
    env = make_env(factory=FakeDevice)
    with pytest.raises(SerialUnavailableError):
        env.service.send_turn(25)
    assert env.devices == []


def test_no_port_configured(make_env, ctx):
    env = make_env(port="")
    assert not env.service.connect()
    assert ctx.state.status("serial") == st.DISCONNECTED
    assert "no configurado" in env.service.get_status().error


def test_open_failure_reports_disconnected(make_env, ctx):
    env = make_env(factory=FakeDevice)
    env.factory_error = serial.SerialException("COM3 ocupado")
    assert not env.service.connect()
    assert env.service.get_status().error == "COM3 ocupado"
    assert ctx.state.status("serial") == st.DISCONNECTED


def test_auto_reconnect_when_port_appears(qtbot, make_env, ctx):
    env = make_env(factory=FakeDevice)
    env.factory_error = serial.SerialException("no existe")
    env.service.start()
    qtbot.waitUntil(lambda: ctx.state.status("serial") == st.DISCONNECTED, timeout=2000)
    env.factory_error = None  # conectan el dispositivo
    qtbot.waitUntil(lambda: ctx.state.status("serial") == st.CONNECTED, timeout=3000)
    assert env.service.is_connected()


def test_mid_send_failure_is_ambiguous_and_disconnects(make_env, ctx):
    env = make_env(factory=lambda: FakeDevice(fail_on_write=2))
    env.service.connect()
    with pytest.raises(SerialSendError):
        env.service.send_turn(25)
    assert env.devices[0].writes == [PACKET_25]  # la 1.ª transmisión salió; no se reintenta sola
    assert not env.service.is_connected()
    assert ctx.state.status("serial") == st.DISCONNECTED
    assert env.devices[0].is_open is False


def test_detects_unplugged_port_and_blocks_send_before_writing(make_env, ctx):
    env = make_env(port="COM3", factory=FakeDevice, listed=["COM3"])
    env.service.connect()
    assert env.service.is_connected()
    env.listed = []  # desconectan el USB
    with pytest.raises(SerialUnavailableError):
        env.service.send_turn(25)  # nada se escribió: reintento seguro
    assert env.devices[0].writes == []
    assert ctx.state.status("serial") == st.DISCONNECTED


def test_health_check_detects_unplug(qtbot, make_env, ctx):
    env = make_env(port="COM3", factory=FakeDevice, listed=["COM3"])
    env.service.start()
    qtbot.waitUntil(lambda: ctx.state.status("serial") == st.CONNECTED, timeout=2000)
    changes = []
    env.service.connection_changed.connect(changes.append)
    env.listed = []
    qtbot.waitUntil(lambda: False in changes, timeout=2000)
    env.listed = ["COM3"]
    qtbot.waitUntil(lambda: ctx.state.status("serial") == st.CONNECTED, timeout=3000)


def test_virtual_port_never_listed_is_not_flagged_lost(make_env):
    env = make_env(port="/dev/pts/7", factory=FakeDevice, listed=[])
    env.service.connect()
    env.service.send_turn(25)
    assert len(env.devices[0].writes) == 2


def test_config_change_reopens_port_only_when_connection_params_change(qtbot, make_env):
    env = make_env(factory=FakeDevice)
    env.service.start()
    qtbot.waitUntil(env.service.is_connected, timeout=2000)
    env.settings = SerialSettings(port="loop://", transmissions=3)  # solo transmisiones
    env.service.on_config_changed()
    assert len(env.devices) == 1
    env.settings = SerialSettings(port="loop://", baudrate=19200, transmissions=3)
    env.service.on_config_changed()
    qtbot.waitUntil(lambda: len(env.devices) == 2 and env.service.is_connected(), timeout=2000)
    assert env.devices[0].is_open is False


def test_turn_pending_while_serial_down_is_processed_when_it_returns(qtbot, make_env, ctx):
    """TurnService + SerialService reales: el turno espera y sale al reconectar el puerto."""

    class Printer:
        printed = []

        def print_ticket(self, turn):
            self.printed.append(turn.message_id)

    env = make_env(factory=FakeDevice)
    env.factory_error = serial.SerialException("sin dispositivo")
    printer = Printer()
    service = TurnService(
        ctx.turns,
        ctx.events,
        ctx.state,
        env.service,
        printer,
        ack_sender=lambda *_: True,
        terminal_id=lambda: "TERM-001",
    )
    env.service.start()
    result = service.handle_message({"message_id": "A", "terminal_id": "TERM-001", "turn": 25})
    assert result.outcome == "PENDING"
    assert ctx.turns.get_by_message_id("A").status == "RECEIVED"

    env.factory_error = None
    qtbot.waitUntil(lambda: ctx.turns.get_by_message_id("A").status == "COMPLETED", timeout=3000)
    assert env.devices[0].writes == [PACKET_25] * 2
    assert printer.printed == ["A"]


def test_diagnostics_serial_actions(make_env, ctx):
    env = make_env(factory=FakeDevice)
    diag = DiagnosticsController(ctx.state, ctx.db, env.service)
    assert not diag.send_test_turn(25).ok  # sin conexión
    assert not diag.send_test_turn(0).ok
    env.service.connect()
    result = diag.send_test_turn(25)
    assert result.ok and result.message == "TX: 99 55 19 (x2)"
    assert diag.test_serial().ok
    assert ctx.turns.search() == []  # el turno de prueba no crea turnos reales


@pytest.mark.skipif(not hasattr(__import__("os"), "openpty"), reason="requiere pty (Linux/macOS)")
def test_real_pyserial_port_through_pty(make_env, ctx):
    """Puerto serial real de pyserial (pseudo-terminal): verifica los bytes en el otro extremo."""
    import os
    import select

    master, slave = os.openpty()
    try:
        env = make_env(port=os.ttyname(slave))
        assert env.service.connect()
        env.service.send_turn(25)
        received = b""
        while len(received) < len(PACKET_25) * 2:  # las dos transmisiones pueden llegar separadas
            ready, _, _ = select.select([master], [], [], 1.0)
            assert ready
            received += os.read(master, 64)
        assert received == PACKET_25 * 2
    finally:
        os.close(master)
        os.close(slave)
