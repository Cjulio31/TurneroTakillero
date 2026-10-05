import pytest

from app.communication.backoff import BackoffPolicy
from app.communication.hub_client import HubClient, HubConnectionError
from app.communication.mock_hub_client import MockHubClient
from app.controllers import app_state as st
from app.services.hub_service import HubService


def test_backoff_sequence_and_cap():
    policy = BackoffPolicy()
    assert [policy.next_delay() for _ in range(8)] == [5, 10, 20, 30, 60, 60, 60, 60]
    policy.reset()
    assert policy.next_delay() == 5
    with pytest.raises(ValueError):
        BackoffPolicy([])


def test_mock_implements_interface():
    assert isinstance(MockHubClient(), HubClient)


def test_mock_delivers_turn_and_duplicate():
    mock = MockHubClient("TERM-001")
    received = []
    mock.on_turn_received(received.append)
    mock.connect()
    first = mock.send_turn(25)
    mock.resend_last()
    assert [m["message_id"] for m in received] == [first["message_id"]] * 2
    assert received[0]["turn"] == 25 and received[0]["terminal_id"] == "TERM-001"


def test_mock_queues_while_disconnected_and_flushes_on_connect():
    mock = MockHubClient()
    received = []
    mock.on_turn_received(received.append)
    mock.send_turn(1)
    assert received == []
    mock.connect()
    assert len(received) == 1


def test_mock_ack_requires_connection():
    mock = MockHubClient()
    with pytest.raises(HubConnectionError):
        mock.send_ack("A", "COMPLETED")
    mock.connect()
    mock.send_ack("A", "COMPLETED")
    assert mock.acks == [("A", "COMPLETED")]


def test_mock_unreachable_refuses_connection():
    mock = MockHubClient()
    mock.reachable = False
    with pytest.raises(HubConnectionError):
        mock.connect()
    assert not mock.is_connected()


def test_mock_invalid_and_burst():
    mock = MockHubClient()
    received = []
    mock.on_turn_received(received.append)
    mock.connect()
    mock.send_invalid()
    mock.send_burst(10, 3)
    assert "message_id" not in received[0]
    assert [m["turn"] for m in received[1:]] == [10, 11, 12]
    assert len({m["message_id"] for m in received[1:]}) == 3


@pytest.fixture
def service(qtbot, ctx):
    mock = MockHubClient()
    svc = HubService(mock, ctx.state, ctx.events, BackoffPolicy([0.01, 0.02, 0.03]))
    yield svc
    svc.stop()


def test_service_connects_and_reports_ready(service, ctx):
    service.start()
    assert ctx.state.status("hub") == st.READY
    assert service.client.ready_sent == 1
    assert ctx.events.recent()[0]["event_type"] == "HUB_CONNECTED"


def test_service_forwards_turns_as_signal(qtbot, service):
    service.start()
    with qtbot.waitSignal(service.turn_received) as blocker:
        service.client.send_turn(7)
    assert blocker.args[0]["turn"] == 7


def test_service_reconnects_after_drop(qtbot, service, ctx):
    service.start()
    service.client.simulate_disconnect()
    assert ctx.state.status("hub") == st.DISCONNECTED
    qtbot.waitUntil(lambda: ctx.state.status("hub") == st.READY, timeout=2000)
    assert service.client.is_connected()
    assert service.backoff.attempt == 0  # se reinició tras reconectar


def test_service_backoff_grows_while_hub_is_down(qtbot, service, ctx):
    service.client.reachable = False
    service.start()
    assert ctx.state.status("hub") == st.DISCONNECTED
    qtbot.waitUntil(lambda: service.backoff.attempt >= 3, timeout=2000)
    service.client.reachable = True
    qtbot.waitUntil(lambda: ctx.state.status("hub") == st.READY, timeout=2000)


def test_service_does_not_reconnect_after_stop(qtbot, service, ctx):
    service.start()
    service.stop()
    qtbot.wait(100)
    assert not service.client.is_connected()
    assert ctx.state.status("hub") == st.DISCONNECTED


def test_service_ack_returns_false_without_channel(service):
    assert service.send_ack("A", "COMPLETED") is False
    service.start()
    assert service.send_ack("A", "COMPLETED") is True


def test_service_error_signal_and_event(qtbot, service, ctx):
    service.start()
    with qtbot.waitSignal(service.hub_error) as blocker:
        service.client.send_error("X1", "boom")
    assert blocker.args == ["X1", "boom"]
    assert ctx.events.recent()[0]["event_type"] == "HUB_ERROR"


def test_turn_arrives_then_hub_drops_turn_still_delivered(qtbot, service):
    """Turno recibido y luego caída: el mensaje ya salió hacia el consumidor."""
    got = []
    service.turn_received.connect(got.append)
    service.start()
    service.client.send_turn(25)
    service.client.simulate_disconnect()
    assert len(got) == 1


def test_diagnostics_test_hub(ctx):
    from app.controllers.diagnostics_controller import DiagnosticsController

    mock = MockHubClient()
    service = HubService(mock, ctx.state, ctx.events)
    diag = DiagnosticsController(ctx.state, ctx.db, hub=service)
    assert not DiagnosticsController(ctx.state, ctx.db).test_hub().ok  # sin servicio

    service.start()
    result = diag.test_hub()
    assert result.ok and result.message == "HUB conectado (simulado)"

    mock.reachable = False
    mock.disconnect()
    service.stop()
    service.start()
    mock.reachable = True
    result = diag.test_hub()  # reintenta de inmediato, sin esperar el backoff
    assert result.ok or "Reintentando" in result.message
    assert mock.is_connected()
    service.stop()
