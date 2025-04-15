import asyncio
import json
import secrets
import threading
from datetime import datetime
from contextlib import asynccontextmanager

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

# defined here so we can ship this as a single .py file
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OVOS Messagebus Monitor</title>
    <style>
        body { font-family: Arial, sans-serif; background: #222; color: #fff; padding: 1em; margin: 0; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.5rem 1rem;
            background-color: #222;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        .header img { height: 40px; }
        .header h1 { color: #f44336; }

        .controls {
            margin-top: 1rem;
            text-align: center;
        }

        .input, select {
            background: #444;
            color: #fff;
            border: 1px solid #666;
            border-radius: 4px;
            padding: 8px 12px;
            margin-right: 0.5em;
            font-size: 0.9em;
            width: 200px;
            display: inline-block;
        }

        .input:focus, select:focus {
            outline: none;
            box-shadow: 0 0 4px #f44336;
        }

        .btn {
            padding: 0.6rem 1rem;
            cursor: pointer;
            border: none;
            border-radius: 4px;
            background-color: rgba(5, 2, 2, 0);
            color: white;
            font-weight: bold;
            margin-top: 0.5rem;
        }

        .btn:hover {
            background-color: #7a1f1f;
        }

        .msg {
            border: 1px solid #666;
            padding: 0.8rem;
            margin-bottom: 1rem;
            background: #333;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
            cursor: pointer;
        }

        .msg-type { color: #f44336; font-weight: bold; }
        .label { color: #bbb; }

        .msg-details {
            display: none;
            padding-top: 1rem;
        }

        .msg-section {
            margin-top: 1rem;
        }

        .msg-section pre {
            margin-top: 0.5rem;
            padding: 10px;
            background: #444;
            border-radius: 5px;
            color: #f8f8f2;
        }

        .msg-section button {
            margin-top: 0.5rem;
            padding: 0.3rem 0.6rem;
            font-size: 0.9em;
            background-color: #444;
            color: #fff;
            border: 1px solid #666;
            border-radius: 4px;
            cursor: pointer;
        }

        .msg-section button:hover {
            background-color: #555;
        }

        footer {
            margin-top: 1rem;
            background-color: #222;
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }

        footer p {
            color: #fff;
            margin: 0;
        }

        /* Prism.js darcula theme */
        .token.comment, .token.prolog, .token.doctype, .token.cdata { color: #7f7f7f; }
        .token.punctuation { color: #f8f8f2; }
        .token.property { color: #f8f8f2; }
        .token.tag { color: #f8f8f2; }
        .token.boolean { color: #ff79c6; }
        .token.number { color: #bd93f9; }
        .token.function { color: #ff79c6; }
        .token.class-name { color: #50fa7b; }
        .token.selector { color: #ff79c6; }
        .token.string { color: #f1fa8c; }
        .token.operator { color: #ffb86c; }
        .token.keyword { color: #ff79c6; }
        .token.variable { color: #8be9fd; }
    </style>

    <!-- Prism.js CSS for Darcula theme -->
    <link href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-okaidia.min.css" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
</head>
<body>

    <header class="header">
        <div>
            <img src="https://www.openvoiceos.org/_next/static/media/logo.02220a9b.png" alt="OVOS Logo">
            <h1>OpenVoiceOS Messagebus Monitor</h1>
        </div>
    </header>

    <div class="controls">
        <input type="text" id="filter" class="input" placeholder="Filter by type">
        <input type="text" id="search" class="input" placeholder="Search content">
        <input type="text" id="session_filter" class="input" placeholder="Filter by session_id">
        <input type="text" id="source_filter" class="input" placeholder="Filter by source">
        <input type="text" id="destination_filter" class="input" placeholder="Filter by destination">
    
        <select id="sort" class="input">
            <option value="desc">Newest First</option>
            <option value="asc">Oldest First</option>
        </select>
        <button class="btn" onclick="downloadJSON()">⬇ Export to JSON</button>
    </div>

    <div class="container">
        <div id="log"></div>
    </div>

    <footer>
        <p>&copy; Copyright 2025 - TigreGóticoLda.</p>
        <button class="btn" onclick="window.open('https://github.com/OpenVoiceOS/OpenVoiceOS/issues', '_blank')" title="Open the issue tracker on GitHub">Report Issue</button>
    </footer>

    <script>
        const log = document.getElementById("log");
        const filterInput = document.getElementById("filter");
        const searchInput = document.getElementById("search");
        const sessionFilterInput = document.getElementById("session_filter");
        const sourceInput = document.getElementById("source_filter");
        const destinationInput = document.getElementById("destination_filter");
        const sortSelect = document.getElementById("sort");
        const messages = [];

        function matchesSearch(msg, text) {
            text = text.toLowerCase();
            return (
                JSON.stringify(msg.type || {}).toLowerCase().includes(text) ||
                JSON.stringify(msg.context || {}).toLowerCase().includes(text) ||
                JSON.stringify(msg.data || {}).toLowerCase().includes(text) ||
                JSON.stringify(msg.destination || {}).toLowerCase().includes(text) ||
                JSON.stringify(msg.source || {}).toLowerCase().includes(text) ||
                JSON.stringify(msg.session || {}).toLowerCase().includes(text) ||
                JSON.stringify(msg.session_data || {}).toLowerCase().includes(text)
            );
        }

        function render() {
            const filterText = filterInput.value.trim().toLowerCase();
            const searchText = searchInput.value.trim().toLowerCase();
            const sessionText = sessionFilterInput.value.trim().toLowerCase();
            const sourceText = sourceInput.value.trim().toLowerCase();
            const destinationText = destinationInput.value.trim().toLowerCase();

            const sortOrder = sortSelect.value;
            log.innerHTML = "";

            const filtered = messages
                .filter(msg =>
                    (!filterText || msg.type.toLowerCase().includes(filterText)) &&
                    (!searchText || matchesSearch(msg, searchText)) &&
                    (!sessionText || JSON.stringify(msg.session || {}).toLowerCase().includes(sessionText)) &&
                    (!sourceText || JSON.stringify(msg.source || {}).toLowerCase().includes(sourceText)) &&
                    (!destinationText || JSON.stringify(msg.destination || {}).toLowerCase().includes(destinationText))
                )
                .sort((a, b) => sortOrder === "asc"
                    ? new Date(a.timestamp) - new Date(b.timestamp)
                    : new Date(b.timestamp) - new Date(a.timestamp));

            for (const msg of filtered) {
                const div = document.createElement("div");
                div.className = "msg";
                div.innerHTML = `
                    <div class="msg-type">${msg.type}</div>
                    <div><span class="label">Timestamp:</span> ${new Date(msg.timestamp).toLocaleString()}</div>
                    
                    <div>
                        ${msg.session ? `<span class="label">session_id:</span> ${msg.session} ` : ""}
                        ${msg.source ? `<span class="label">| source:</span> ${msg.source} ` : ""}
                        ${msg.destination ? `<span class="label">| destination:</span> ${msg.destination}` : ""}
                    </div>

                    ${Object.keys(msg.data || {}).length ? `
                    <div class="msg-section">
                        <button class="btn" onclick="toggleVisibility('data-${msg.timestamp}')">message.data</button>
                        <div id="data-${msg.timestamp}" class="msg-details" style="display: none;">
                            <div><span class="label">Data:</span><pre class="language-json">${JSON.stringify(msg.data, null, 2)}</pre></div>
                        </div>
                    </div>` : ""}
                    
                    ${Object.keys(msg.context || {}).length ? `
                    <div class="msg-section">
                        <button class="btn" onclick="toggleVisibility('context-${msg.timestamp}')">message.context</button>
                        <div id="context-${msg.timestamp}" class="msg-details" style="display: none;">
                            <div><span class="label">Context:</span><pre class="language-json">${JSON.stringify(msg.context, null, 2)}</pre></div>
                        </div>
                    </div>` : ""}
                    
                    ${Object.keys(msg.session_data || {}).length ? `
                    <div class="msg-section">
                        <button class="btn" onclick="toggleVisibility('session-${msg.timestamp}')">session</button>
                        <div id="session-${msg.timestamp}" class="msg-details" style="display: none;">
                            <div><span class="label">Session:</span><pre class="language-json">${JSON.stringify(msg.session_data, null, 2)}</pre></div>
                        </div>
                    </div>` : ""}

                `;
                log.appendChild(div);

                // Apply syntax highlighting to the pre elements
                Prism.highlightAll();
            }
        }


        function toggleVisibility(id) {
            const el = document.getElementById(id);
            if (!el) return;
            el.style.display = el.style.display === "block" ? "none" : "block";
        }


        filterInput.addEventListener("input", render);
        searchInput.addEventListener("input", render);
        sourceInput.addEventListener("input", render);
        destinationInput.addEventListener("input", render);
        sessionFilterInput.addEventListener("input", render);
        sortSelect.addEventListener("change", render);

        const ws = new WebSocket(`ws://${location.host}/ws`);
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            messages.push(msg);
            render();
        };

        function downloadJSON() {
            const json = JSON.stringify(messages, null, 2);
            const blob = new Blob([json], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "bus_messages.json";
            a.click();
            URL.revokeObjectURL(url);
        }
    </script>
</body>
</html>

"""

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
    return HTMLResponse(HTML)


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
