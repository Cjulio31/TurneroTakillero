from urllib.parse import urlsplit

_SECURE = {"wss", "https"}
_PLAIN = {"ws", "http"}
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def ensure_secure_url(url: str, schemes: tuple[str, ...]) -> str:
    """Valida la URL del HUB. Solo HTTPS/WSS; HTTP/WS únicamente hacia la propia máquina.

    Devuelve la URL sin espacios. Lanza ValueError si no es válida o no es segura.
    """
    url = url.strip()
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in _SECURE | _PLAIN or not parts.hostname:
        raise ValueError("La URL del HUB debe iniciar con https://, wss://, http:// o ws://")
    if scheme not in schemes:
        raise ValueError(
            f"Este transporte requiere una URL {' o '.join(s + '://' for s in schemes)}"
        )
    if scheme in _PLAIN and parts.hostname.lower() not in _LOOPBACK:
        raise ValueError(
            "Un HUB remoto debe usar HTTPS/WSS: el token no puede viajar sin cifrar "
            "(solo localhost admite http/ws)"
        )
    return url
