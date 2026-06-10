"""Unit tests for message type glob filtering."""
import pytest
from ovos_busmon.buffer import CapturedMessage, RingBuffer
from ovos_busmon.filters import filter_by_type, matches_glob


def _msg(msg_type: str) -> CapturedMessage:
    return CapturedMessage(
        id=1, timestamp="2025-01-01T00:00:00+00:00",
        msg_type=msg_type, data={}, context={},
    )


@pytest.mark.parametrize("pattern,msg_type,expected", [
    ("*", "anything.here", True),
    ("", "anything.here", True),
    ("ovos.*", "ovos.session.update", True),
    ("ovos.*", "speak", False),
    ("speak", "speak", True),
    ("speak", "SPEAK", True),          # case-insensitive
    ("ovos.?ession.*", "ovos.session.update", True),
    ("ovos.?ession.*", "ovos.xession.update", True),
    ("ovos.?ession.*", "ovos.session", False),
    ("recognizer_loop:*", "recognizer_loop:utterance", True),
    ("recognizer_loop:*", "speak", False),
])
def test_matches_glob(pattern, msg_type, expected):
    assert matches_glob(msg_type, pattern) == expected


def test_filter_by_type_wildcard():
    msgs = [_msg("speak"), _msg("ovos.foo"), _msg("ovos.bar")]
    assert filter_by_type(msgs, "*") == msgs
    assert filter_by_type(msgs, "") == msgs


def test_filter_by_type_prefix():
    msgs = [_msg("speak"), _msg("ovos.foo"), _msg("ovos.bar")]
    result = filter_by_type(msgs, "ovos.*")
    assert len(result) == 2
    assert all(m.msg_type.startswith("ovos.") for m in result)


def test_filter_by_type_exact():
    msgs = [_msg("speak"), _msg("ovos.foo")]
    result = filter_by_type(msgs, "speak")
    assert len(result) == 1
    assert result[0].msg_type == "speak"
