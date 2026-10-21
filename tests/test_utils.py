import logging

from app.database.event_repository import EventRepository
from app.utils.logger import setup_logging
from app.utils.validators import is_valid_message_id, is_valid_turn


def test_turn_validation():
    assert is_valid_turn(1) and is_valid_turn(255)
    assert not is_valid_turn(0)
    assert not is_valid_turn(256)
    assert not is_valid_turn("25")
    assert not is_valid_turn(True)


def test_message_id_validation():
    assert is_valid_message_id("abc")
    assert not is_valid_message_id("")
    assert not is_valid_message_id(None)


def test_logging_writes_file_and_is_idempotent(tmp_path):
    path = tmp_path / "logs" / "app.log"
    setup_logging(path)
    setup_logging(path)
    logging.getLogger("t").info("hola")
    handlers = [h for h in logging.getLogger().handlers if getattr(h, "_turnos_handler", False)]
    assert len(handlers) == 1
    handlers[0].flush()
    assert "hola" in path.read_text(encoding="utf-8")


def test_events(db):
    repo = EventRepository(db)
    repo.add("HUB_CONNECTED", "ok")
    assert repo.recent()[0]["event_type"] == "HUB_CONNECTED"


def test_resolve_base_dir(monkeypatch, tmp_path):
    from pathlib import Path

    from app.utils import constants

    monkeypatch.delenv("TURNOS_HOME", raising=False)
    assert (constants.resolve_base_dir() / "run.py").exists()  # desarrollo: raíz del repo

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert constants.resolve_base_dir() == tmp_path / "TurnosDesktop"  # empaquetado

    monkeypatch.setenv("TURNOS_HOME", str(tmp_path / "custom"))
    assert constants.resolve_base_dir() == Path(tmp_path / "custom")  # el override manda


def test_clear_logs_removes_active_and_rotated_and_keeps_logging(tmp_path):
    from app.utils.logger import clear_logs

    path = tmp_path / "logs" / "app.log"
    setup_logging(path)
    logging.getLogger("t").info("antes")
    (tmp_path / "logs" / "app.log.1").write_text("viejo" * 100)
    (tmp_path / "logs" / "otro.txt").write_text("no tocar")

    deleted, size = clear_logs(path)
    assert deleted == 2 and size > 500
    assert not (tmp_path / "logs" / "app.log.1").exists()
    assert (tmp_path / "logs" / "otro.txt").exists()
    text = path.read_text()
    assert "antes" not in text and "Logs borrados" in text  # sigue registrando tras borrar

    logging.getLogger("t").info("despues")
    assert "despues" in path.read_text()


def test_excepthook_logs_uncaught_exceptions(caplog):
    import sys

    from app.utils.logger import install_excepthook

    original = sys.excepthook
    try:
        sys.excepthook = lambda *_: None  # pytest-qt hace fallar el test si se invoca el suyo
        install_excepthook()
        install_excepthook()  # idempotente: no se envuelve dos veces
        with caplog.at_level("CRITICAL", logger="app.unhandled"):
            try:
                raise ValueError("boom en un slot")
            except ValueError:
                sys.excepthook(*sys.exc_info())
        records = [r for r in caplog.records if r.name == "app.unhandled"]
        assert len(records) == 1  # un solo registro: el gancho no quedó envuelto dos veces
        assert records[0].exc_info[0] is ValueError
    finally:
        sys.excepthook = original


def test_single_instance_blocks_second_and_frees_on_release(tmp_path):
    from app.utils.single_instance import SingleInstance

    path = tmp_path / "sub" / "turnos.lock"
    first, second = SingleInstance(path), SingleInstance(path)
    assert first.acquire()
    assert not second.acquire()
    first.release()
    assert second.acquire()
    second.release()
