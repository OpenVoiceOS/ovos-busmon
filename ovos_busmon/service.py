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
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ovos_busmon.buffer import CapturedMessage, RingBuffer
from ovos_busmon.version import __version__

load_dotenv()

OVOS_BUS_HOST = os.getenv("OVOS_BUS_HOST", "localhost")
OVOS_BUS_PORT = int(os.getenv("OVOS_BUS_PORT", "8181"))
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", "2000"))

USERNAME = os.getenv("BUSMON_USERNAME", os.getenv("USERNAME", "ovos"))
PASSWORD = os.getenv("BUSMON_PASSWORD", os.getenv("PASSWORD", "ovos"))

STATIC_DIR = Path(__file__).parent.parent / "static"

# Global ring buffer and SSE subscriber set
_buffer: RingBuffer = RingBuffer(maxlen=BUFFER_SIZE)
_subscribers: set[asyncio.Queue] = set()


# ─── SSE helpers ─────────────────────────────────────────────────────────────

async def _broadcast_to_sse(payload: dict) -> None:
    dead = set()
    for q in _subscribers:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.add(q)
    _subscribers.difference_update(dead)


# ─── Bus connection lifecycle ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from ovos_bus_client import Message
    from ovos_bus_client.client import AsyncMessageBusClient
    from ovos_bus_client.session import SessionManager

    bus = AsyncMessageBusClient(host=OVOS_BUS_HOST, port=OVOS_BUS_PORT)

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

from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic(auto_error=False)


def _verify(credentials: Optional[HTTPBasicCredentials] = Depends(_security)):
    if not USERNAME and not PASSWORD:
        return None  # auth disabled
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    ok = (
        secrets.compare_digest(credentials.username, USERNAME)
        and secrets.compare_digest(credentials.password, PASSWORD)
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="ovos-busmon", version=__version__, lifespan=lifespan)


class SendRequest(BaseModel):
    type: str
    data: dict = {}
    context: dict = {}


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
        from ovos_bus_client.client import AsyncMessageBusClient

        bus = AsyncMessageBusClient(host=OVOS_BUS_HOST, port=OVOS_BUS_PORT)
        await bus.connect()
        await bus.emit(Message(req.type, req.data, req.context))
        await bus.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Bus unavailable: {e}")
    return {"ok": True}


# Serve the static UI at /  — must be LAST so API routes are registered first
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    import uvicorn

    host = os.getenv("BUSMON_HOST", "127.0.0.1")
    port = int(os.getenv("BUSMON_PORT", "8005"))
    uvicorn.run("ovos_busmon.service:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
