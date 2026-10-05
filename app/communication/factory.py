from urllib.parse import urlsplit

from app.communication.hub_client import HubClient
from app.communication.mock_hub_client import MockHubClient
from app.communication.rest_hub_client import RestHubClient
from app.communication.websocket_hub_client import WebSocketHubClient
from app.models.configuration import Configuration
from app.utils import constants


def create_hub_client(cfg: Configuration) -> HubClient:
    """Elige el transporte según la URL del HUB configurada.

    Sin URL: HUB simulado (desarrollo). ``wss://``/``ws://``: WebSocket. ``https://``/``http://``:
    REST. Lanza ValueError si la URL no es válida o no es segura (HTTP/WS remoto).
    """
    terminal_id = cfg.terminal_id or constants.DEFAULT_TERMINAL_ID
    url = cfg.hub_url.strip()
    if not url:
        return MockHubClient(terminal_id)
    common = {
        "token": cfg.api_token,
        "terminal_id": terminal_id,
        "terminal_name": cfg.terminal_name,
        "terminal_location": cfg.terminal_location,
        "app_version": constants.APP_VERSION,
        "timeout": cfg.hub_timeout,
    }
    if urlsplit(url).scheme.lower() in ("ws", "wss"):
        return WebSocketHubClient(url, **common)
    return RestHubClient(url, **common)
