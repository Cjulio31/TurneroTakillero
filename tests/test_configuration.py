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
