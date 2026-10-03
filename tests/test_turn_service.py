import pytest

from app.communication.backoff import BackoffPolicy
from app.communication.mock_hub_client import MockHubClient
from app.controllers import app_state as st
from app.database.turn_repository import TurnRepository
from app.services import turn_service as ts
from app.services.errors import PrintError, SerialSendError, SerialUnavailableError
from app.services.hub_service import HubService
from app.services.turn_service import TurnService
from app.utils import constants


class FakeSerial:
    def __init__(self):
        self.sent = []
        self.error = None

    def send_turn(self, turn_number):
        if self.error:
            raise self.error
        self.sent.append(turn_number)


class FakePrinter:
    def __init__(self):
        self.printed = []
        self.error = None

    def print_ticket(self, turn):
        if self.error:
            raise self.error
        self.printed.append(turn.message_id)


class Env:
    """TurnService con dispositivos falsos y un HUB cuyo ACK se puede cortar."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.serial = FakeSerial()
        self.printer = FakePrinter()
        self.hub_up = True
        self.acks = []
        self.service = TurnService(
            ctx.turns,
            ctx.events,
            ctx.state,
            self.serial,
            self.printer,
            ack_sender=self._ack,
            terminal_id=lambda: "TERM-001",
        )

    def _ack(self, message_id, status):
        if not self.hub_up:
            return False
        self.acks.append((message_id, status))
        return True

    def msg(self, mid="A", turn=25, **extra):
        return {"message_id": mid, "terminal_id": "TERM-001", "turn": turn, **extra}

    def status(self, mid="A"):
        return self.ctx.turns.get_by_message_id(mid).status


@pytest.fixture
def env(qtbot, ctx):
    return Env(ctx)


def test_happy_path(env):
    result = env.service.handle_message(env.msg())
    assert result.outcome == ts.OUTCOME_COMPLETED
    assert env.serial.sent == [25] and env.printer.printed == ["A"]
    turn = env.ctx.turns.get_by_message_id("A")
    assert turn.status == "COMPLETED"
    assert all([turn.processed_at, turn.sent_at, turn.printed_at, turn.completed_at])
    assert env.acks == [("A", "COMPLETED")]
    assert turn.ack_status == "COMPLETED" and turn.acked_at
    assert env.ctx.state.last_received and env.ctx.state.last_printed


def test_invalid_message_is_rejected_and_not_stored(env):
    result = env.service.handle_message(env.msg(turn=300))
    assert result.outcome == ts.OUTCOME_REJECTED and result.detail == "INVALID_TURN"
    assert env.ctx.turns.search() == []
    assert env.serial.sent == []
    assert env.acks == [("A", "REJECTED")]
    assert env.ctx.events.recent()[0]["event_type"] == constants.EVENT_TURN_REJECTED


def test_wrong_terminal_rejected(env):
    payload = {**env.msg(), "terminal_id": "TERM-002"}
    assert env.service.handle_message(payload).detail == "WRONG_TERMINAL"
    assert env.printer.printed == []


def test_duplicate_does_not_print_again_and_confirms_previous_state(env):
    """Prueba crítica de duplicados (sección 52)."""
    env.service.handle_message(env.msg())
    result = env.service.handle_message(env.msg())
    assert result.outcome == ts.OUTCOME_DUPLICATE
    assert env.serial.sent == [25] and env.printer.printed == ["A"]
    assert env.acks == [("A", "COMPLETED"), ("A", "COMPLETED")]
    assert len(env.ctx.turns.search()) == 1


def test_duplicate_of_in_flight_turn_is_not_processed(env):
    env.serial.error = SerialUnavailableError("sin puerto")
    env.service.handle_message(env.msg())
    env.serial.error = None
    assert env.service.handle_message(env.msg()).outcome == ts.OUTCOME_DUPLICATE
    assert env.serial.sent == []  # lo procesará process_pending, no el duplicado
    assert env.status() == "RECEIVED"


def test_print_error_keeps_turn_and_retry_does_not_resend_serial(env):
    """Impresora desconectada (sección 55)."""
    env.printer.error = PrintError("sin papel")
    result = env.service.handle_message(env.msg())
    assert result.outcome == ts.OUTCOME_ERROR and result.detail == "PRINT_ERROR"
    turn = env.ctx.turns.get_by_message_id("A")
    assert (turn.status, turn.error_code, turn.error_message) == (
        "ERROR",
        "PRINT_ERROR",
        "sin papel",
    )
    assert env.serial.sent == [25]
    assert env.acks[-1] == ("A", "ERROR")

    env.printer.error = None
    retried = env.service.retry("A")
    assert retried.outcome == ts.OUTCOME_COMPLETED
    assert env.serial.sent == [25]  # el serial NO se reenvió
    assert env.printer.printed == ["A"]
    assert env.status() == "COMPLETED"
    assert env.acks[-1] == ("A", "COMPLETED")
    assert env.ctx.turns.get_by_message_id("A").error_code is None


def test_unexpected_printer_exception_is_error_not_crash(env):
    env.printer.error = RuntimeError("driver roto")
    assert env.service.handle_message(env.msg()).outcome == ts.OUTCOME_ERROR


def test_serial_unavailable_keeps_turn_pending_then_processes_on_reconnect(env):
    env.serial.error = SerialUnavailableError("COM3 desconectado")
    result = env.service.handle_message(env.msg())
    assert result.outcome == ts.OUTCOME_PENDING
    turn = env.ctx.turns.get_by_message_id("A")
    assert (turn.status, turn.error_code) == ("RECEIVED", "SERIAL_UNAVAILABLE")
    assert env.printer.printed == []

    env.serial.error = None
    env.ctx.state.set_status("serial", st.CONNECTED)  # reconexión del dispositivo
    assert env.status() == "COMPLETED"
    assert env.serial.sent == [25] and env.printer.printed == ["A"]


def test_pending_turns_processed_in_order_and_stop_while_serial_down(env):
    env.serial.error = SerialUnavailableError("down")
    for i, mid in enumerate(["A", "B", "C"], start=1):
        env.service.handle_message(env.msg(mid, i))
    assert env.service.process_pending() == 0
    env.serial.error = None
    assert env.service.process_pending() == 3
    assert env.serial.sent == [1, 2, 3]


def test_ambiguous_serial_error_goes_to_error_without_blind_retry(env):
    env.serial.error = SerialSendError("USB se desconectó durante el envío")
    result = env.service.handle_message(env.msg())
    assert result.outcome == ts.OUTCOME_ERROR and result.detail == "SERIAL_ERROR"
    assert env.service.process_pending() == 0  # no se reintenta solo
    assert env.serial.sent == []
    assert env.status() == "ERROR"


def test_retry_only_for_error_and_never_completed(env):
    env.service.handle_message(env.msg())
    assert env.service.retry("A") is None  # COMPLETED: jamás se reprocesa
    assert env.service.retry("NOPE") is None
    assert env.serial.sent == [25] and env.printer.printed == ["A"]


def test_ack_failure_then_sync_when_hub_returns(env):
    env.hub_up = False
    env.service.handle_message(env.msg())
    assert env.status() == "COMPLETED" and env.acks == []
    assert env.ctx.turns.get_by_message_id("A").acked_at is None

    env.hub_up = True
    env.ctx.state.set_status("hub", st.READY)  # HUB listo -> sincroniza
    assert env.acks == [("A", "COMPLETED")]
    assert env.ctx.turns.list_unacked() == []
    env.ctx.state.set_status("hub", st.DISCONNECTED)
    env.ctx.state.set_status("hub", st.READY)
    assert env.acks == [("A", "COMPLETED")]  # ya confirmado: no se reenvía ni se reprocesa
    assert env.printer.printed == ["A"]


def test_hub_down_after_receiving_still_completes(env):
    """Prueba de desconexión (sección 53)."""
    env.service.handle_message(env.msg())  # recibido
    env.hub_up = False  # el HUB se cae
    env.service.handle_message(env.msg("B", 26))
    assert env.status("B") == "COMPLETED"


def test_recovery_after_restart(env):
    """Prueba de reinicio (sección 54): estados intermedios tras un cierre inesperado."""
    repo: TurnRepository = env.ctx.turns
    for mid, status in [
        ("R", "RECEIVED"),
        ("P", "PROCESSING"),
        ("S", "SENT"),
        ("I", "PRINTED"),
        ("E", "ERROR"),
        ("C", "COMPLETED"),
    ]:
        repo.add(mid, "TERM-001", 10)
        repo.update_status(mid, status)
    counts = env.service.startup()
    assert counts == {"to_error": 2, "completed": 1}
    assert env.status("P") == "ERROR" and env.status("S") == "ERROR"
    assert env.ctx.turns.get_by_message_id("P").error_code == "INTERRUPTED"
    assert env.status("I") == "COMPLETED"
    assert env.status("R") == "COMPLETED"  # RECEIVED nunca se envió: se procesa
    assert env.status("E") == "ERROR"  # queda para reintento manual
    assert env.serial.sent == [10]  # solo R se envió; nada se reprocesó a ciegas
    assert env.printer.printed == ["R"]


def test_sync_acks_final_states_after_recovery(env):
    env.ctx.turns.add("I", "TERM-001", 10)
    env.ctx.turns.update_status("I", "PRINTED")
    env.service.recover_on_startup()
    env.service.sync_pending_acks()
    assert env.acks == [("I", "COMPLETED")]


def test_turn_changed_signal(qtbot, env):
    with qtbot.waitSignal(env.service.turn_changed):
        env.service.handle_message(env.msg())


def test_end_to_end_with_mock_hub(qtbot, ctx):
    """HUB simulado -> HubService -> TurnService -> serial/impresora -> ACK al HUB."""
    mock = MockHubClient("TERM-001")
    hub = HubService(mock, ctx.state, ctx.events, BackoffPolicy([0.01]))
    serial, printer = FakeSerial(), FakePrinter()
    service = TurnService(
        ctx.turns,
        ctx.events,
        ctx.state,
        serial,
        printer,
        ack_sender=hub.send_ack,
        terminal_id=lambda: "TERM-001",
    )
    hub.turn_received.connect(service.handle_message)
    hub.start()

    first = mock.send_turn(25)
    mock.resend_last()  # duplicado
    mock.send_invalid()
    assert serial.sent == [25] and printer.printed == [first["message_id"]]
    assert mock.acks == [(first["message_id"], "COMPLETED")] * 2

    mock.simulate_disconnect()
    mock.send_turn(26)  # el HUB lo entrega al reconectar
    assert serial.sent == [25]
    qtbot.waitUntil(lambda: serial.sent == [25, 26], timeout=2000)
    hub.stop()
