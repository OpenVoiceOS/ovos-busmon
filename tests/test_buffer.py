"""Unit tests for RingBuffer."""
import json
import pytest
from ovos_busmon.buffer import CapturedMessage, RingBuffer


def _msg(id_: int, msg_type: str = "test.msg") -> CapturedMessage:
    return CapturedMessage(
        id=id_,
        timestamp="2025-01-01T00:00:00+00:00",
        msg_type=msg_type,
        data={"n": id_},
        context={},
    )


def test_append_and_len():
    buf = RingBuffer(maxlen=10)
    buf.append(_msg(1))
    buf.append(_msg(2))
    assert len(buf) == 2


def test_ring_eviction():
    buf = RingBuffer(maxlen=3)
    for i in range(1, 6):
        buf.append(_msg(i))
    assert len(buf) == 3
    ids = [m.id for m in buf]
    assert ids == [3, 4, 5]


def test_since_id_pagination():
    buf = RingBuffer(maxlen=100)
    for i in range(1, 11):
        buf.append(_msg(i))
    result = buf.since(since_id=5)
    assert [m.id for m in result] == [6, 7, 8, 9, 10]


def test_since_id_zero_returns_all():
    buf = RingBuffer(maxlen=100)
    for i in range(1, 6):
        buf.append(_msg(i))
    assert len(buf.since(0)) == 5


def test_since_with_limit():
    buf = RingBuffer(maxlen=100)
    for i in range(1, 11):
        buf.append(_msg(i))
    result = buf.since(since_id=0, limit=3)
    assert len(result) == 3
    # limit returns last N
    assert result[-1].id == 10


def test_next_id_monotonic():
    buf = RingBuffer()
    ids = [buf.next_id() for _ in range(5)]
    assert ids == list(range(1, 6))


def test_export_jsonl_shape():
    buf = RingBuffer(maxlen=10)
    for i in range(1, 4):
        buf.append(_msg(i, f"type.{i}"))
    jsonl = buf.export_jsonl()
    lines = [l for l in jsonl.split("\n") if l.strip()]
    assert len(lines) == 3
    for line in lines:
        obj = json.loads(line)
        assert "id" in obj
        assert "type" in obj
        assert "data" in obj
        assert "timestamp" in obj


def test_clear():
    buf = RingBuffer(maxlen=10)
    buf.append(_msg(1))
    buf.clear()
    assert len(buf) == 0


def test_to_dict_keys():
    msg = _msg(42, "speak")
    d = msg.to_dict()
    for key in ("id", "timestamp", "type", "data", "context", "session", "source", "destination"):
        assert key in d
