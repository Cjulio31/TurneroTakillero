import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve

from app.communication import hub_protocol as proto
from app.communication.backoff import BackoffPolicy
from app.communication.factory import create_hub_client
from app.communication.hub_client import HubConnectionError
from app.communication.hub_url import ensure_secure_url
from app.communication.rest_hub_client import RestHubClient
from app.communication.websocket_hub_client import WebSocketHubClient
from app.controllers import app_state as st
from app.main import build_hub_client
from app.models.configuration import Configuration
from app.services.hub_service import HubService


def wait_for(condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return False


# --- seguridad de la URL ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "url", ["wss://hub.example.com/ws", "https://hub.example.com", "ws://localhost:8080"]
)
def test_secure_urls_accepted(url):
    assert ensure_secure_url(url, ("wss", "ws", "https", "http")) == url


@pytest.mark.parametrize(
    "url", ["ws://hub.example.com", "http://10.0.0.5", "ftp://x", "hub.example.com", "https://"]
)
def test_insecure_or_invalid_urls_rejected(url):
    with pytest.raises(ValueError):
        ensure_secure_url(url, ("wss", "ws", "https", "http"))


def test_scheme_must_match_transport():
    with pytest.raises(ValueError, match="requiere"):
        ensure_secure_url("https://hub.example.com", ("wss", "ws"))


# --- WebSocket ------------------------------------------------------------------------------
class FakeWsHub:
    """HUB WebSocket real (websockets) en localhost para probar el cliente de extremo a extremo."""

    def __init__(self):
        self.frames: list[dict] = []
        self.auth: list[str | None] = []
        self.sockets = []
        self.to_send_on_register: list[str] = []
        self.server = serve(self._handler, "127.0.0.1", 0)
        self.url = f"ws://127.0.0.1:{self.server.socket.getsockname()[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _handler(self, ws):
        self.sockets.append(ws)
        self.auth.append(ws.request.headers.get("Authorization"))
        try:
            for raw in ws:
                frame = json.loads(raw)
                self.frames.append(frame)
                if frame["type"] == proto.T_REGISTER:
                    for text in self.to_send_on_register:
                        ws.send(text)
        except ConnectionClosed:
            pass

    def push(self, text: str):
        self.sockets[-1].send(text)

    def drop(self):
        # close() espera el cierre TCP del cliente (hasta 10 s): se hace aparte para no frenar
        threading.Thread(target=self.sockets[-1].close, daemon=True).start()

    def close(self):
        # shutdown() espera los cierres de socket pendientes (hasta 10 s): no frena la suite
        threading.Thread(target=self.server.shutdown, daemon=True).start()


@pytest.fixture
def ws_hub():
    hub = FakeWsHub()
    yield hub
    hub.close()


def make_ws_client(url, **kwargs):
    return WebSocketHubClient(
        url, "tok", "T1", "Caja 1", "Piso 2", "9.9", timeout=3, ping_interval=5, **kwargs
    )


def test_ws_connect_registers_with_bearer_token(ws_hub):
    client = make_ws_client(ws_hub.url)
    changes = []
    client.on_connection_changed(changes.append)
    client.connect()
    try:
        assert client.is_connected() and changes == [True]
        assert wait_for(lambda: ws_hub.frames)
        register = ws_hub.frames[0]
        assert register["type"] == proto.T_REGISTER and register["terminal_id"] == "T1"
        assert (register["name"], register["location"], register["app_version"]) == (
            "Caja 1",
            "Piso 2",
            "9.9",
        )
        assert ws_hub.auth == ["Bearer tok"]
    finally:
        client.disconnect()


def test_ws_receives_turns_errors_and_answers_ping(ws_hub):
    client = make_ws_client(ws_hub.url)
    turns, errors = [], []
    client.on_turn_received(turns.append)
    client.on_error(lambda code, msg: errors.append((code, msg)))
    client.connect()
    try:
        message = {"message_id": "A", "terminal_id": "T1", "turn": 25}
        ws_hub.push(proto.encode(proto.T_TURN, data=message))
        ws_hub.push("esto no es json")  # se ignora sin romper la conexión
        ws_hub.push(proto.encode(proto.T_TURN, data="no-dict"))
        ws_hub.push(proto.encode(proto.T_ERROR, code="E1", message="boom"))
        ws_hub.push(proto.encode(proto.T_PING))
        assert wait_for(lambda: turns and errors)
        assert turns == [message] and errors == [("E1", "boom")]
        assert wait_for(lambda: any(f["type"] == proto.T_PONG for f in ws_hub.frames))
        assert client.is_connected()
    finally:
        client.disconnect()


def test_ws_ack_and_ready_reach_hub(ws_hub):
    client = make_ws_client(ws_hub.url)
    client.connect()
    try:
        client.send_ready()
        client.send_ack("A", "COMPLETED")
        assert wait_for(lambda: len(ws_hub.frames) >= 3)
        kinds = [f["type"] for f in ws_hub.frames]
        assert kinds == [proto.T_REGISTER, proto.T_READY, proto.T_ACK]
        ack = ws_hub.frames[2]
        assert (ack["message_id"], ack["status"], ack["terminal_id"]) == ("A", "COMPLETED", "T1")
    finally:
        client.disconnect()


def test_ws_ack_without_connection_raises():
    client = make_ws_client("ws://127.0.0.1:9")
    with pytest.raises(HubConnectionError):
        client.send_ack("A", "COMPLETED")


def test_ws_unreachable_hub_raises():
    client = WebSocketHubClient("ws://127.0.0.1:9", "", "T1", timeout=1)
    with pytest.raises(HubConnectionError):
        client.connect()
    assert not client.is_connected()


def test_ws_server_drop_notifies_disconnect_and_can_reconnect(ws_hub):
    client = make_ws_client(ws_hub.url)
    changes = []
    client.on_connection_changed(changes.append)
    client.connect()
    try:
        ws_hub.drop()
        assert wait_for(lambda: changes == [True, False])
        assert not client.is_connected()
        client.connect()
        assert client.is_connected() and changes == [True, False, True]
    finally:
        client.disconnect()


def test_ws_intentional_disconnect_notifies_once(ws_hub):
    client = make_ws_client(ws_hub.url)
    changes = []
    client.on_connection_changed(changes.append)
    client.connect()
    client.disconnect()
    time.sleep(0.2)
    assert changes == [True, False] and not client.is_connected()


def test_ws_refuses_remote_plain_url():
    with pytest.raises(ValueError):
        WebSocketHubClient("ws://hub.example.com", "", "T1")


# --- REST -----------------------------------------------------------------------------------
class FakeRestHub:
    def __init__(self):
        self.requests: list[tuple[str, str, dict | None, str | None]] = []
        self.pending: list[dict] = []
        self.status = 200
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                outer.requests.append(
                    (self.command, self.path, body, self.headers.get("Authorization"))
                )
                if outer.status != 200:
                    self.send_response(outer.status)
                    self.end_headers()
                    return
                payload = b"[]"
                if self.command == "GET":
                    batch, outer.pending = outer.pending, []
                    payload = json.dumps(batch).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = _handle

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/api"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def rest_hub():
    hub = FakeRestHub()
    yield hub
    hub.close()


def make_rest_client(url):
    return RestHubClient(url, "tok", "T 1", "Caja", "Piso", "9.9", timeout=2, poll_interval=0.05)


def test_rest_register_poll_and_ack(rest_hub):
    client = make_rest_client(rest_hub.url)
    turns, changes = [], []
    client.on_turn_received(turns.append)
    client.on_connection_changed(changes.append)
    client.connect()
    try:
        method, path, body, auth = rest_hub.requests[0]
        assert (method, path, auth) == ("POST", "/api/terminals/T%201/register", "Bearer tok")
        assert body["terminal_id"] == "T 1" and body["app_version"] == "9.9"
        message = {"message_id": "A", "terminal_id": "T 1", "turn": 7}
        rest_hub.pending = [message, "basura"]
        assert wait_for(lambda: turns)
        assert turns == [message] and changes == [True]

        client.send_ack("a/b", "COMPLETED")
        ack = next(r for r in rest_hub.requests if r[1].endswith("/ack"))
        assert ack[:3] == (
            "POST",
            "/api/messages/a%2Fb/ack",
            {"terminal_id": "T 1", "status": "COMPLETED"},
        )
    finally:
        client.disconnect()
    assert changes == [True, False]


def test_rest_auth_rejected_and_unreachable(rest_hub):
    rest_hub.status = 401
    client = make_rest_client(rest_hub.url)
    with pytest.raises(HubConnectionError, match="Autenticación"):
        client.connect()
    assert not client.is_connected()
    with pytest.raises(HubConnectionError):
        make_rest_client("http://127.0.0.1:9").connect()
    with pytest.raises(HubConnectionError):
        client.send_ack("A", "COMPLETED")


def test_rest_lost_connection_is_reported(rest_hub):
    client = make_rest_client(rest_hub.url)
    changes = []
    client.on_connection_changed(changes.append)
    client.connect()
    rest_hub.status = 500  # el siguiente poll falla
    assert wait_for(lambda: changes == [True, False])
    assert not client.is_connected()


def test_rest_refuses_remote_plain_url():
    with pytest.raises(ValueError):
        RestHubClient("http://hub.example.com", "", "T1")


# --- fábrica y HubService --------------------------------------------------------------------
def test_factory_chooses_transport_by_url():
    from app.communication.mock_hub_client import MockHubClient

    assert isinstance(create_hub_client(Configuration()), MockHubClient)
    assert isinstance(
        create_hub_client(Configuration(hub_url="wss://hub.example.com", terminal_id="T")),
        WebSocketHubClient,
    )
    assert isinstance(
        create_hub_client(Configuration(hub_url="https://hub.example.com", terminal_id="T")),
        RestHubClient,
    )
    with pytest.raises(ValueError):
        create_hub_client(Configuration(hub_url="ws://hub.example.com"))


def test_invalid_hub_url_falls_back_to_mock_and_logs_event(ctx):
    from app.communication.mock_hub_client import MockHubClient

    ctx.config_service.save(Configuration(hub_url="ws://hub.example.com", terminal_id="T"))
    assert isinstance(build_hub_client(ctx), MockHubClient)
    assert any("inválida" in e["message"] for e in ctx.events.recent())


def test_hub_service_end_to_end_over_websocket(qtbot, ctx, ws_hub):
    client = make_ws_client(ws_hub.url)
    service = HubService(client, ctx.state, ctx.events, BackoffPolicy([0.05]))
    received = []
    service.turn_received.connect(received.append)
    service.start()
    try:
        qtbot.waitUntil(lambda: ctx.state.status("hub") == st.READY, timeout=5000)
        message = {"message_id": "A", "terminal_id": "T1", "turn": 25}
        ws_hub.push(proto.encode(proto.T_TURN, data=message))
        qtbot.waitUntil(lambda: received == [message], timeout=5000)
        assert service.send_ack("A", "COMPLETED") is True
        assert wait_for(lambda: any(f["type"] == proto.T_ACK for f in ws_hub.frames))
        assert any(f["type"] == proto.T_READY for f in ws_hub.frames)

        ws_hub.drop()  # caída: debe reconectar solo
        qtbot.waitUntil(lambda: ctx.state.status("hub") == st.DISCONNECTED, timeout=5000)
        qtbot.waitUntil(lambda: ctx.state.status("hub") == st.READY, timeout=5000)
    finally:
        service.stop()
    assert ctx.state.status("hub") == st.DISCONNECTED


def test_hub_service_retries_while_hub_is_down(qtbot, ctx):
    client = WebSocketHubClient("ws://127.0.0.1:9", "", "T1", timeout=0.5)
    service = HubService(client, ctx.state, ctx.events, BackoffPolicy([0.05]))
    service.start()
    try:
        qtbot.waitUntil(lambda: ctx.state.status("hub") == st.CONNECTING, timeout=3000)
        qtbot.wait(300)
        assert ctx.state.status("hub") in (st.CONNECTING, st.DISCONNECTED)
        assert ctx.state.status("hub") != st.READY
    finally:
        service.stop()
