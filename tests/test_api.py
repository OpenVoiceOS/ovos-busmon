"""E2E tests for the FastAPI service against a fake bus."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Patch ovos_bus_client before importing service so the lifespan
# bus connect does not try to reach a real bus.
import sys, types

# Stub ovos_bus_client so tests run without a real OVOS bus.
# Always replace the client submodule because the real installed package
# lacks AsyncMessageBusClient (it was removed in 2.x) and we don't want
# any network activity during tests.

class _Msg:
    def __init__(self, msg_type, data=None, context=None):
        self.msg_type = msg_type
        self.data = data or {}
        self.context = context or {}

    @staticmethod
    def deserialize(raw):
        d = json.loads(raw)
        return _Msg(d["type"], d.get("data", {}), d.get("context", {}))


class _AsyncBus:
    def __init__(self, **kw): self._handlers = {}
    async def connect(self): pass
    async def close(self): pass
    def on(self, event, cb): self._handlers[event] = cb
    def remove(self, event, cb): self._handlers.pop(event, None)
    async def emit(self, msg): pass


class _Sess:
    session_id = "test-session"
    def serialize(self): return {"session_id": "test-session"}


class _SM:
    @staticmethod
    def get(msg): return _Sess()


# Ensure top-level module has Message
import ovos_bus_client as _obc_top
if not hasattr(_obc_top, "Message"):
    _obc_top.Message = _Msg

# Unconditionally inject AsyncMessageBusClient into the client submodule
import ovos_bus_client.client as _obc_client
_obc_client.AsyncMessageBusClient = _AsyncBus

# Inject SessionManager stub into session submodule
import ovos_bus_client.session as _obc_sess
if not hasattr(_obc_sess, "SessionManager"):
    _obc_sess.SessionManager = _SM

from ovos_busmon.service import app, _buffer, _subscribers


@pytest_asyncio.fixture
async def client():
    _buffer.clear()
    _subscribers.clear()
    # Use default creds (ovos/ovos) — set via env defaults in service.py
    import base64
    creds = base64.b64encode(b"ovos:ovos").decode()
    headers = {"Authorization": f"Basic {creds}"}
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_status(client):
    r = await client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "buffered" in data


@pytest.mark.asyncio
async def test_messages_empty(client):
    r = await client.get("/api/messages")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_messages_pagination(client):
    from ovos_busmon.buffer import CapturedMessage
    for i in range(1, 11):
        msg = CapturedMessage(
            id=_buffer.next_id(),
            timestamp="2025-01-01T00:00:00+00:00",
            msg_type=f"type.{i}",
            data={"n": i},
            context={},
        )
        _buffer.append(msg)

    r = await client.get("/api/messages?since_id=5")
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()]
    assert all(i > 5 for i in ids)

    r2 = await client.get("/api/messages?since_id=0&limit=3")
    assert len(r2.json()) == 3


@pytest.mark.asyncio
async def test_export_jsonl(client):
    from ovos_busmon.buffer import CapturedMessage
    for i in range(1, 4):
        _buffer.append(CapturedMessage(
            id=_buffer.next_id(),
            timestamp="2025-01-01T00:00:00+00:00",
            msg_type=f"t.{i}", data={}, context={},
        ))

    r = await client.get("/api/export")
    assert r.status_code == 200
    lines = [l for l in r.text.split("\n") if l.strip()]
    assert len(lines) == 3
    for line in lines:
        obj = json.loads(line)
        assert "type" in obj and "id" in obj


@pytest.mark.asyncio
async def test_send_validation(client):
    # Missing type
    r = await client.post("/api/send", json={"data": {}})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_send_ok(client):
    """POST /api/send should return 202 — uses the stubbed AsyncMessageBusClient."""
    r = await client.post("/api/send", json={"type": "speak", "data": {"utterance": "hello"}})
    assert r.status_code == 202
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_sse_stream_broadcasts():
    """Messages pushed via _broadcast_to_sse appear in a subscriber queue."""
    from ovos_busmon.service import _broadcast_to_sse, _subscribers

    q: asyncio.Queue = asyncio.Queue(maxsize=10)
    _subscribers.add(q)
    try:
        payload = {"id": 1, "type": "speak", "data": {}, "context": {},
                   "timestamp": "2025-01-01T00:00:00+00:00",
                   "session": None, "session_data": {}, "source": None, "destination": None}
        await _broadcast_to_sse(payload)
        assert not q.empty()
        received = q.get_nowait()
        assert received["type"] == "speak"
    finally:
        _subscribers.discard(q)
