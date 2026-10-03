class SerialUnavailableError(Exception):
    """El puerto serial no está disponible: NO se envió nada. Es seguro reintentar."""


class SerialSendError(Exception):
    """Falló el envío serial y no se sabe si el dispositivo recibió algo (sin ACK).

    No se debe reintentar a ciegas: requiere decisión explícita.
    """


class PrintError(Exception):
    """Falló la impresión del ticket."""
