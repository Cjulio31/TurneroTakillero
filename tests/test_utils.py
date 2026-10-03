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
