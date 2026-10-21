from app.database.config_repository import ConfigRepository
from app.models.configuration import Configuration
from app.services.configuration_service import ConfigurationService


def test_defaults_and_roundtrip(db):
    svc = ConfigurationService(ConfigRepository(db))
    assert svc.load().baudrate == 9600
    assert not svc.is_terminal_configured()

    cfg = Configuration(hub_url="https://hub", terminal_id="TERM-001", serial_port="COM3")
    svc.save(cfg)
    loaded = svc.load()
    assert loaded == cfg
    assert svc.is_terminal_configured()


def test_set_overwrites(db):
    repo = ConfigRepository(db)
    repo.set("k", "1")
    repo.set("k", "2")
    assert repo.get("k") == "2"
    assert repo.get("missing", "d") == "d"


def test_print_tickets_flag_defaults_on_and_persists_off(db):
    svc = ConfigurationService(ConfigRepository(db))
    assert svc.load().print_tickets is True  # por defecto se imprime
    svc.save(Configuration(print_tickets=False))
    assert svc.load().print_tickets is False  # int("False") fallaba y volvía al default
    svc.save(Configuration(print_tickets=True))
    assert svc.load().print_tickets is True


def test_serial_header_persists_and_is_validated(db):
    from app.controllers.config_controller import ConfigController

    svc = ConfigurationService(ConfigRepository(db))
    assert (svc.load().serial_header_1, svc.load().serial_header_2) == (153, 85)
    ConfigController(svc).update(serial_header_1=16, serial_header_2=0)
    assert (svc.load().serial_header_1, svc.load().serial_header_2) == (16, 0)
    for bad in (-1, 256):
        try:
            ConfigController(svc).update(serial_header_2=bad)
        except ValueError as exc:
            assert "0 y 255" in str(exc)
        else:
            raise AssertionError("debió rechazar la cabecera")
    assert svc.load().serial_header_2 == 0  # lo inválido no se guardó
