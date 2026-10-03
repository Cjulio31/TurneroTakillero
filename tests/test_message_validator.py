import pytest

from app.protocol import message_validator as mv


def _msg(**overrides):
    return {"message_id": "A", "terminal_id": "TERM-001", "turn": 25, **overrides}


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ("texto", mv.MALFORMED),
        (None, mv.MALFORMED),
        ({"terminal_id": "TERM-001", "turn": 1}, mv.MISSING_MESSAGE_ID),
        (_msg(message_id=""), mv.MISSING_MESSAGE_ID),
        (_msg(message_id=5), mv.MISSING_MESSAGE_ID),
        ({"message_id": "A", "turn": 1}, mv.MISSING_TERMINAL_ID),
        (_msg(terminal_id="TERM-999"), mv.WRONG_TERMINAL),
        ({"message_id": "A", "terminal_id": "TERM-001"}, mv.MISSING_TURN),
        (_msg(turn=0), mv.INVALID_TURN),
        (_msg(turn=256), mv.INVALID_TURN),
        (_msg(turn="25"), mv.INVALID_TURN),
        (_msg(turn=True), mv.INVALID_TURN),
        (_msg(turn=2.5), mv.INVALID_TURN),
    ],
)
def test_rejections(payload, code):
    with pytest.raises(mv.MessageRejected) as exc:
        mv.parse_message(payload, "TERM-001")
    assert exc.value.code == code


def test_rejection_keeps_message_id_when_known():
    with pytest.raises(mv.MessageRejected) as exc:
        mv.parse_message(_msg(turn=0), "TERM-001")
    assert exc.value.message_id == "A"


def test_valid_message_with_defaults_and_extras():
    msg = mv.parse_message(
        _msg(priority=2, created_at="2026-10-03T12:30:00", metadata={"x": 1}), "TERM-001"
    )
    assert (msg.message_id, msg.turn, msg.priority, msg.metadata) == ("A", 25, 2, {"x": 1})
    bare = mv.parse_message(_msg(priority="alta", metadata="no"), "TERM-001")
    assert bare.priority == 0 and bare.metadata == {}


def test_boundaries_accepted():
    assert mv.parse_message(_msg(turn=1), "TERM-001").turn == 1
    assert mv.parse_message(_msg(turn=255), "TERM-001").turn == 255
