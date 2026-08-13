"""E2E tests for the FastAPI service against a fake bus."""
from __future__ import annotations

import asyncio
import json

# Patch ovos_bus_client before importing service so the lifespan
# bus connect does not try to reach a real bus.
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

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

from ovos_busmon.service import _buffer, _subscribers, app


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
    lines = [ln for ln in r.text.split("\n") if ln.strip()]
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
    """POST /api/send emits through the persistent capture bus and returns 202."""
    import ovos_busmon.service as svc

    class _Bus:
        connected = True

        async def emit(self, msg):
            pass

    with patch.object(svc, "_capture_bus", _Bus()):
        r = await client.post("/api/send", json={"type": "speak", "data": {"utterance": "hello"}})
    assert r.status_code == 202
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_send_503_when_bus_not_connected(client):
    """A dead/absent capture bus must fail fast to 503 — never hang the request
    or open a throwaway per-request client that reconnects forever."""
    import ovos_busmon.service as svc

    with patch.object(svc, "_capture_bus", None):
        r = await client.post("/api/send", json={"type": "speak", "data": {}})
    assert r.status_code == 503

    class _Down:
        connected = False

        async def emit(self, msg):
            raise AssertionError("must not emit on a disconnected bus")

    with patch.object(svc, "_capture_bus", _Down()):
        r = await client.post("/api/send", json={"type": "speak", "data": {}})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_async_client_bus_treated_as_connected(client):
    """A bus exposing no connection indicator (the AsyncMessageBusClient shape:
    connect/close/on/remove/emit only) must be treated as connected so inject
    and chat work — not permanently 503'd once PR #200 ships."""
    import ovos_busmon.service as svc

    class _AsyncShape:
        async def connect(self):
            pass

        async def emit(self, m):
            pass

    with patch.object(svc, "_capture_bus", _AsyncShape()):
        r = await client.post("/api/send", json={"type": "speak", "data": {}})
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_auth_off_by_default():
    """With no token or username/password configured, the API is open (the
    loopback dev default). There are NO default credentials anymore."""
    import ovos_busmon.service as svc
    assert not svc._auth_configured()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as c:
        r = await c.get("/api/status")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_token_auth_enforced_when_set(monkeypatch):
    """When BUSMON_TOKEN is set, a mutating endpoint rejects a request with no
    token and accepts one via ?token= or Authorization: Bearer."""
    import ovos_busmon.service as svc
    monkeypatch.setattr(svc, "TOKEN", "s3cret")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as c:
        # no token -> 401
        r = await c.post("/api/chat", json={"utterance": "hi", "session_id": "s1"})
        assert r.status_code == 401
        # wrong token -> 401
        r = await c.post("/api/chat?token=nope",
                         json={"utterance": "hi", "session_id": "s1"})
        assert r.status_code == 401
        # correct token via query param
        r = await c.get("/api/status?token=s3cret")
        assert r.status_code == 200
        # correct token via Authorization: Bearer
        r = await c.get("/api/status", headers={"Authorization": "Bearer s3cret"})
        assert r.status_code == 200


def test_require_auth_or_exit():
    """A non-loopback bind without any auth must refuse to start; loopback, or a
    non-loopback bind WITH auth, must be allowed."""
    import pytest as _pt

    import ovos_busmon.service as svc
    # non-loopback + no auth -> SystemExit(2)
    svc.TOKEN = svc.USERNAME = svc.PASSWORD = ""
    with _pt.raises(SystemExit) as ei:
        svc._require_auth_or_exit("0.0.0.0")
    assert ei.value.code == 2
    # loopback + no auth -> allowed
    svc._require_auth_or_exit("127.0.0.1")
    # non-loopback + token -> allowed
    svc.TOKEN = "s3cret"
    try:
        svc._require_auth_or_exit("0.0.0.0")
    finally:
        svc.TOKEN = ""


@pytest.mark.asyncio
async def test_chat_rejects_empty_utterance(client):
    r = await client.post("/api/chat", json={"utterance": "   ", "session_id": "s1"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_chat_rejects_missing_session_id(client):
    r = await client.post("/api/chat", json={"utterance": "hi"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_chat_payload_shape(client):
    """The emitted Message must be shaped exactly like a real text client
    builds it (ovos-say-to / ovos-simple-cli): recognizer_loop:utterance
    with {"utterances": [text], "lang": lang}, and a Session embedded in
    context["session"] carrying the *same* session_id sent by the client
    (never "default"), so converse/multi-turn context works across turns.
    """
    from ovos_busmon import service as svc

    captured = {}

    class _RecordingBus:
        connected = True

        def __init__(self, **kw):
            pass

        async def connect(self):
            pass

        async def close(self):
            pass

        async def emit(self, msg):
            captured["msg_type"] = msg.msg_type
            captured["data"] = msg.data
            captured["context"] = msg.context

    with patch.object(svc, "_capture_bus", _RecordingBus()):
        r = await client.post(
            "/api/chat",
            json={"utterance": "what time is it", "lang": "en-us", "session_id": "chat-abc123"},
        )

    assert r.status_code == 202
    assert r.json()["ok"] is True
    assert captured["msg_type"] == "recognizer_loop:utterance"
    assert captured["data"] == {"utterances": ["what time is it"], "lang": "en-us"}
    sess = captured["context"]["session"]
    assert sess["session_id"] == "chat-abc123"
    assert sess["session_id"] != "default"
    # SESSION-1: empty pipeline == omission — busmon must NOT push its own
    # (client-side default) pipeline into the server's session.
    assert sess.get("pipeline", []) == []


@pytest.mark.asyncio
async def test_chat_honors_client_declared_session(client):
    """When the client sends an explicit `session` dict (the busmon Session
    editor), it is honored verbatim in context["session"] — including
    site_id/pipeline — and the utterance lang follows the session's lang."""
    from ovos_busmon import service as svc

    captured = {}

    class _RecordingBus:
        connected = True

        def __init__(self, **kw):
            pass

        async def connect(self):
            pass

        async def close(self):
            pass

        async def emit(self, msg):
            captured["data"] = msg.data
            captured["context"] = msg.context

    session = {
        "session_id": "sess-kitchen", "lang": "pt-PT",
        "site_id": "kitchen", "pipeline": ["stop_high", "padatious_high"],
    }
    with patch.object(svc, "_capture_bus", _RecordingBus()):
        r = await client.post(
            "/api/chat",
            json={
                "utterance": "que horas são", "lang": "en-us",
                "session_id": "sess-kitchen", "session": session,
            },
        )

    assert r.status_code == 202
    sess = captured["context"]["session"]
    assert sess["site_id"] == "kitchen"
    assert sess["pipeline"] == ["stop_high", "padatious_high"]
    assert sess["session_id"] == "sess-kitchen"
    assert sess["lang"] == "pt-PT"
    # The utterance lang follows the declared session, not the top-level default.
    assert captured["data"]["lang"] == "pt-PT"


@pytest.mark.asyncio
async def test_chat_empty_session_uses_default_build(client):
    """An explicit empty session {} is treated as 'not declared': the server
    builds its default Session with the pipeline suppressed (SESSION-1), not the
    verbatim-honor path."""
    from ovos_busmon import service as svc

    captured = {}

    class _RecordingBus:
        connected = True

        def __init__(self, **kw):
            pass

        async def connect(self):
            pass

        async def close(self):
            pass

        async def emit(self, msg):
            captured["context"] = msg.context

    with patch.object(svc, "_capture_bus", _RecordingBus()):
        r = await client.post(
            "/api/chat",
            json={"utterance": "hi", "session_id": "s1", "session": {}},
        )
    assert r.status_code == 202
    sess = captured["context"]["session"]
    assert sess["session_id"] == "s1"
    assert sess.get("pipeline", []) == []


@pytest.mark.asyncio
async def test_chat_speak_reply_reaches_stream_for_matching_session():
    """A mocked ``speak`` reply carrying the same session_id used by
    /api/chat must reach the SSE stream (what the chat panel filters on
    client-side to render an assistant bubble).
    """
    from ovos_busmon.buffer import CapturedMessage
    from ovos_busmon.service import _broadcast_to_sse, _subscribers

    session_id = "chat-abc123"
    q: asyncio.Queue = asyncio.Queue(maxsize=10)
    _subscribers.add(q)
    try:
        payload = CapturedMessage(
            id=1,
            timestamp="2025-01-01T00:00:00+00:00",
            msg_type="speak",
            data={"utterance": "It is noon."},
            context={"session": {"session_id": session_id}},
            session=session_id,
        ).to_dict()
        await _broadcast_to_sse(payload)

        assert not q.empty()
        received = q.get_nowait()
        assert received["type"] == "speak"
        assert received["session"] == session_id
        assert received["data"]["utterance"] == "It is noon."

        # A speak for a *different* session must not be mistaken as ours —
        # the client-side filter (msg.session === chatSessionId) relies on
        # this same field.
        other = CapturedMessage(
            id=2,
            timestamp="2025-01-01T00:00:01+00:00",
            msg_type="speak",
            data={"utterance": "not for you"},
            context={"session": {"session_id": "someone-else"}},
            session="someone-else",
        ).to_dict()
        await _broadcast_to_sse(other)
        received2 = q.get_nowait()
        assert received2["session"] != session_id
    finally:
        _subscribers.discard(q)


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


@pytest.mark.asyncio
async def test_slow_sse_consumer_is_not_dropped():
    """A subscriber whose queue is full keeps its subscription and receives the
    newest payload (oldest queued item is dropped instead of the subscriber)."""
    import ovos_busmon.service as svc
    svc._subscribers.clear()
    q = asyncio.Queue(maxsize=1)
    q.put_nowait({"seq": "old"})  # queue now full
    svc._subscribers.add(q)
    await svc._broadcast_to_sse({"seq": "new"})
    assert q in svc._subscribers, "slow-but-alive subscriber must stay subscribed"
    assert q.get_nowait() == {"seq": "new"}, "newest payload must be delivered"
    svc._subscribers.clear()
