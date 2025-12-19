import asyncio
import json
import secrets
import threading
from datetime import datetime
from contextlib import asynccontextmanager
import pathlib

from fastapi import FastAPI, WebSocket, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from ovos_bus_client import MessageBusClient, Message
from ovos_bus_client.session import SessionManager
from starlette.websockets import WebSocketState

import os
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv("USERNAME", "ovos")
PASSWORD = os.getenv("PASSWORD", "ovos")


app = FastAPI()
security = HTTPBasic()
websocket_clients = set()
main_loop = None

IGNORE_LIST = ["ovos.session.update_default"]
GUI = ["gui.status.request"]


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, USERNAME)
    correct_password = secrets.compare_digest(credentials.password, PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/", response_class=HTMLResponse)
async def index(username: str = Depends(verify_credentials)):
    file = open(pathlib.Path(__file__).parent / "templates" / "index.html", "r")
    return HTMLResponse(file.read())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        websocket_clients.remove(websocket)


def broadcast(message: dict):
    global main_loop
    data = json.dumps(message)
    for ws in list(websocket_clients):
        if main_loop and ws.application_state == WebSocketState.CONNECTED:
            asyncio.run_coroutine_threadsafe(ws.send_text(data), main_loop)


def run_bus_monitor():
    client = MessageBusClient()

    def echo(msg: str):
        m: Message = Message.deserialize(msg)
        sess = SessionManager.get(m)
        source = m.context.get("source") if m.context else None
        dest = m.context.get("destination") if m.context else None
        standalone_keys = ["session", "source", "destination"]
        message_data = {
            "timestamp": datetime.now().isoformat(),
            "type": m.msg_type,
            "session": sess.session_id,
            "session_data": sess.serialize(),
            "source": source,
            "destination": dest,
            "context": {k: v for k, v in m.context.items() if k not in standalone_keys} if m.context else {},
            "data": m.data or {},
        }
        broadcast(message_data)

    client.on("message", echo)

    def run_client():
        client.run_forever()

    threading.Thread(target=run_client, daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    run_bus_monitor()
    yield


app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
