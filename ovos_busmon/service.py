"""ovos-busmon FastAPI service — Mode 2 transport."""
from __future__ import annotations

import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ovos_busmon.buffer import CapturedMessage, RingBuffer
from ovos_busmon.version import __version__

load_dotenv()

# ─── Bus client compatibility shim ─────────────────────────────────────────────
# ovos_bus_client.client.AsyncMessageBusClient only exists in unmerged
# ovos-bus-client PR #200. Every published release only ships the threaded/sync
# MessageBusClient, so importing AsyncMessageBusClient unconditionally makes
# every real install of this package crash with an ImportError. Prefer the
# async client when it is available (nothing else needs to change once
# PR #200 merges and ships) and otherwise bridge the sync client onto the
# asyncio event loop.
try:
    from ovos_bus_client.client import AsyncMessageBusClient  # noqa: F401
    _HAS_ASYNC_BUS_CLIENT = True
except ImportError:
    AsyncMessageBusClient = None  # type: ignore[assignment]
    _HAS_ASYNC_BUS_CLIENT = False


class _ThreadedBusClientAdapter:
    """Adapts the synchronous/threaded ``MessageBusClient`` to the small async
    surface this module needs (``connect``/``close``/``on``/``remove``/``emit``),
    matching ``AsyncMessageBusClient`` closely enough that call sites don't need
    to know which one they got. The real client runs its blocking websocket
    loop in a background thread; callbacks registered via ``on`` are bounced
    back onto the asyncio event loop with ``call_soon_threadsafe`` so they run
    on the loop like the native async client's callbacks would.
    """

    def __init__(self, host: str, port: int):
        from ovos_bus_client.client import MessageBusClient

        self._bus = MessageBusClient(host=host, port=port)
        self._loop = asyncio.get_event_loop()
        self._bridged: dict = {}

    def on(self, event: str, cb) -> None:
        def _bridge(raw=None):
            self._loop.call_soon_threadsafe(cb, raw)

        self._bridged[cb] = _bridge
        self._bus.on(event, _bridge)

    def remove(self, event: str, cb) -> None:
        bridged = self._bridged.pop(cb, None)
        if bridged is not None:
            self._bus.remove(event, bridged)

    async def connect(self) -> None:
        self._bus.run_in_thread()
        await self._loop.run_in_executor(
            None, lambda: self._bus.connected_event.wait(timeout=5)
        )

    async def close(self) -> None:
        await self._loop.run_in_executor(None, self._bus.close)

    async def emit(self, message) -> None:
        await self._loop.run_in_executor(None, self._bus.emit, message)


def _make_bus(host: str, port: int):
    """Return the preferred bus client for this ovos-bus-client install."""
    if _HAS_ASYNC_BUS_CLIENT:
        return AsyncMessageBusClient(host=host, port=port)
    return _ThreadedBusClientAdapter(host=host, port=port)

OVOS_BUS_HOST = os.getenv("OVOS_BUS_HOST", "localhost")
OVOS_BUS_PORT = int(os.getenv("OVOS_BUS_PORT", "8181"))
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", "2000"))

# No default credentials. Auth is OFF unless a token or a username/password is
# configured. The old code defaulted both to "ovos" (and read the shell's
# USERNAME/PASSWORD env), which shipped a well-known credential: on a
# non-loopback bind anyone could POST /api/send and inject bus messages. The
# default is removed; a non-loopback bind now REQUIRES auth (see main()).
USERNAME = os.getenv("BUSMON_USERNAME", "")
PASSWORD = os.getenv("BUSMON_PASSWORD", "")
# A shared-secret token. Unlike HTTP Basic, a token can travel on the SSE
# (EventSource) URL as ?token=, so authentication and the live UI can coexist —
# HTTP Basic could not, which silently pushed people to run with auth off.
TOKEN = os.getenv("BUSMON_TOKEN", "")

# 0.0.0.0 / :: are wildcard binds (all interfaces) — deliberately NOT loopback,
# so they require auth.
_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def _auth_configured() -> bool:
    return bool(TOKEN or USERNAME or PASSWORD)

STATIC_DIR = Path(__file__).parent.parent / "static"

# Global ring buffer and SSE subscriber set
_buffer: RingBuffer = RingBuffer(maxlen=BUFFER_SIZE)
_subscribers: set[asyncio.Queue] = set()


# ─── SSE helpers ─────────────────────────────────────────────────────────────

async def _broadcast_to_sse(payload: dict) -> None:
    for q in _subscribers:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            # A momentarily slow consumer must not be silently and permanently
            # unsubscribed (that dropped ALL its future messages). Drop its
            # OLDEST queued item to make room and keep it live; a truly
            # disconnected client is removed by the /api/stream generator's
            # finally, not here.
            try:
                q.get_nowait()
                q.put_nowait(payload)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass


# ─── Bus connection lifecycle ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from ovos_bus_client import Message
    from ovos_bus_client.session import SessionManager

    bus = _make_bus(OVOS_BUS_HOST, OVOS_BUS_PORT)

    def _on_raw(raw: str) -> None:
        try:
            m = Message.deserialize(raw)
        except Exception:
            return
        try:
            sess = SessionManager.get(m)
            sess_id = sess.session_id
            sess_data = sess.serialize()
        except Exception:
            sess_id = None
            sess_data = {}

        ctx = m.context or {}
        standalone = {"session", "source", "destination"}
        payload = CapturedMessage(
            id=_buffer.next_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            msg_type=m.msg_type,
            data=m.data or {},
            context={k: v for k, v in ctx.items() if k not in standalone},
            session=sess_id,
            session_data=sess_data,
            source=ctx.get("source"),
            destination=(
                ",".join(ctx["destination"])
                if isinstance(ctx.get("destination"), list)
                else ctx.get("destination")
            ),
        )
        _buffer.append(payload)
        asyncio.create_task(_broadcast_to_sse(payload.to_dict()))

    bus.on("message", _on_raw)
    try:
        await bus.connect()
    except Exception:
        pass  # allow startup even if bus is not available
    try:
        yield
    finally:
        bus.remove("message", _on_raw)
        try:
            await bus.close()
        except Exception:
            pass


# ─── Auth ─────────────────────────────────────────────────────────────────────

_security = HTTPBasic(auto_error=False)


def _verify(request: Request,
            credentials: Optional[HTTPBasicCredentials] = Depends(_security)):
    if not _auth_configured():
        return None  # auth disabled (the loopback dev default)
    # A token authenticates via ?token= (which the SSE EventSource URL can
    # carry) or Authorization: Bearer. compare_digest is done on bytes: on str
    # it rejects non-ASCII and a crafted value would raise TypeError (a 500).
    if TOKEN:
        tok = request.query_params.get("token")
        if not tok:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                tok = auth[7:].strip()
        if tok and secrets.compare_digest(tok.encode(), TOKEN.encode()):
            return "token"
    # HTTP Basic, when a username/password is configured.
    if (USERNAME or PASSWORD) and credentials:
        if (secrets.compare_digest(credentials.username.encode(), USERNAME.encode())
                and secrets.compare_digest(credentials.password.encode(), PASSWORD.encode())):
            return credentials.username
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Basic"},
    )


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="ovos-busmon", version=__version__, lifespan=lifespan)


class SendRequest(BaseModel):
    type: str
    data: dict = {}
    context: dict = {}


class ChatRequest(BaseModel):
    utterance: str
    lang: str = "en-us"
    session_id: str
    # Optional client-declared Session (busmon Session editor). When present it
    # is honored verbatim (only session_id/lang are backfilled); when absent the
    # server builds a default Session from session_id + lang.
    session: Optional[dict] = None


@app.get("/api/status")
async def api_status(_: str = Depends(_verify)):
    return {
        "version": __version__,
        "buffered": len(_buffer),
        "buffer_capacity": _buffer.maxlen,
        "bus_host": OVOS_BUS_HOST,
        "bus_port": OVOS_BUS_PORT,
    }


@app.get("/api/messages")
async def api_messages(
    since_id: int = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=10000),
    _: str = Depends(_verify),
):
    msgs = _buffer.since(since_id=since_id, limit=limit)
    return [m.to_dict() for m in msgs]


@app.get("/api/stream")
async def api_stream(_: str = Depends(_verify)):
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _subscribers.add(q)

    async def event_gen():
        try:
            while True:
                msg = await q.get()
                yield {"data": json.dumps(msg)}
        except asyncio.CancelledError:
            pass
        finally:
            _subscribers.discard(q)

    return EventSourceResponse(event_gen())


@app.get("/api/export")
async def api_export(_: str = Depends(_verify)):
    content = _buffer.export_jsonl()
    return Response(
        content=content,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="bus_messages.jsonl"'},
    )


@app.post("/api/send", status_code=202)
async def api_send(req: SendRequest, _: str = Depends(_verify)):
    try:
        from ovos_bus_client import Message

        bus = _make_bus(OVOS_BUS_HOST, OVOS_BUS_PORT)
        await bus.connect()
        await bus.emit(Message(req.type, req.data, req.context))
        await bus.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Bus unavailable: {e}")
    return {"ok": True}


@app.post("/api/chat", status_code=202)
async def api_chat(req: ChatRequest, _: str = Depends(_verify)):
    """Emit a text utterance built exactly like a real text client (e.g.
    ``ovos-say-to`` / ``ovos-simple-cli``): ``recognizer_loop:utterance`` with
    ``{"utterances": [text], "lang": lang}`` and a Session embedded in
    ``context["session"]`` so the pipeline treats every turn from the same
    browser session as one conversation (multi-turn / converse works).
    """
    utterance = req.utterance.strip()
    if not utterance:
        raise HTTPException(status_code=422, detail="utterance must not be empty")
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(status_code=422, detail="session_id must not be empty")

    try:
        from ovos_bus_client import Message
        from ovos_bus_client.session import Session

        if req.session:
            # A non-empty client-declared Session (busmon Session editor) is
            # honored verbatim; an empty {} is treated as "not declared" and
            # falls through to the default build (which suppresses pipeline).
            # Backfill session_id and lang so pipeline and reply correlation work.
            sess_dict = dict(req.session)
            sess_dict.setdefault("session_id", req.session_id)
            sess_dict.setdefault("lang", req.lang)
            context = {"source": "ovos-busmon-chat", "session": sess_dict}
            lang = sess_dict.get("lang", req.lang)
        else:
            sess = Session(session_id=req.session_id, lang=req.lang)
            # SESSION-1: an empty pipeline list means "use the server's default".
            # Serializing this client's default pipeline would override the
            # core's configured pipeline with plugins that may not exist there.
            sess.pipeline = []
            context = {"source": "ovos-busmon-chat", "session": sess.serialize()}
            lang = req.lang
        msg = Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": lang},
            context,
        )

        bus = _make_bus(OVOS_BUS_HOST, OVOS_BUS_PORT)
        await bus.connect()
        await bus.emit(msg)
        await bus.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Bus unavailable: {e}")
    return {"ok": True}


# Serve the static UI at /  — must be LAST so API routes are registered first
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


# ─── Entry point ─────────────────────────────────────────────────────────────

def _require_auth_or_exit(host: str) -> None:
    """Refuse to expose an unauthenticated monitor beyond loopback.

    ovos-busmon can inject bus messages (speak, shutdown, config), so an open
    non-loopback bind is a remote-control hole. Bind a loopback address for
    zero-auth local use, or set BUSMON_TOKEN (or BUSMON_USERNAME/PASSWORD).
    """
    if host not in _LOOPBACK_HOSTS and not _auth_configured():
        import sys
        print(
            f"ERROR: refusing to bind non-loopback host {host!r} without "
            f"authentication. Set BUSMON_TOKEN (recommended) or "
            f"BUSMON_USERNAME/BUSMON_PASSWORD, or bind a loopback address.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def main():
    import uvicorn

    host = os.getenv("BUSMON_HOST", "127.0.0.1")
    port = int(os.getenv("BUSMON_PORT", "8005"))
    _require_auth_or_exit(host)
    uvicorn.run("ovos_busmon.service:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
