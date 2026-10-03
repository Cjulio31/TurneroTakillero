import pytest

from app.database.turn_repository import TurnRepository
from app.utils import constants


@pytest.fixture
def repo(db):
    return TurnRepository(db)


def test_add_and_get(repo):
    turn = repo.add("ABC", "TERM-001", 25)
    assert turn.status == constants.STATUS_RECEIVED
    assert repo.get_by_message_id("ABC").turn_number == 25


def test_duplicate_message_id_returns_none(repo):
    assert repo.add("ABC", "TERM-001", 25) is not None
    assert repo.add("ABC", "TERM-001", 25) is None
    assert len(repo.search()) == 1


def test_update_status_sets_timestamp_and_error(repo):
    repo.add("ABC", "TERM-001", 25)
    repo.update_status("ABC", constants.STATUS_PROCESSING)
    assert repo.get_by_message_id("ABC").processed_at is not None
    repo.update_status("ABC", constants.STATUS_ERROR, "PRINT", "sin papel")
    t = repo.get_by_message_id("ABC")
    assert (t.status, t.error_code, t.error_message) == ("ERROR", "PRINT", "sin papel")


def test_update_status_invalid_or_missing(repo):
    repo.add("ABC", "TERM-001", 25)
    with pytest.raises(ValueError):
        repo.update_status("ABC", "NOPE")
    with pytest.raises(KeyError):
        repo.update_status("ZZZ", constants.STATUS_SENT)


def test_list_pending_excludes_completed(repo):
    for i, mid in enumerate(["A", "B", "C"], start=1):
        repo.add(mid, "TERM-001", i)
    repo.update_status("A", constants.STATUS_COMPLETED)
    repo.update_status("B", constants.STATUS_PROCESSING)
    assert [t.message_id for t in repo.list_pending()] == ["B", "C"]


def test_search_filters(repo):
    repo.add("A", "TERM-001", 1)
    repo.add("B", "TERM-001", 2)
    repo.update_status("B", constants.STATUS_COMPLETED)
    assert [t.message_id for t in repo.search(status="COMPLETED")] == ["B"]
    assert [t.message_id for t in repo.search(turn_number=1)] == ["A"]
    assert repo.last().message_id == "B"


def test_persists_across_reconnect(tmp_path):
    from app.database.database import Database

    path = tmp_path / "t.db"
    db1 = Database(path)
    TurnRepository(db1).add("A", "TERM-001", 7)
    TurnRepository(db1).update_status("A", constants.STATUS_PROCESSING)
    db1.close()
    db2 = Database(path)
    assert [t.message_id for t in TurnRepository(db2).list_pending()] == ["A"]
    db2.close()
