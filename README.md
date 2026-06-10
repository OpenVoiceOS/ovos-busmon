# ovos-busmon

Live monitor, capture, and injection tool for the [OpenVoiceOS](https://openvoiceos.org) messagebus.
Stream every bus message to a browser, filter by type (glob), inspect payloads, export captures as JSONL, and inject messages directly from the UI.

![screenrecording](demo.gif)

## Two transport modes — one UI

### Mode 1 — fully in-browser (zero server)

Open `static/index.html` directly (or deploy it to GitHub Pages).
The page opens a WebSocket **directly to the OVOS messagebus** (`ws://localhost:8181/core` by default).
Configure host/port/path via the connection panel in the UI or via query parameters:

```
file:///path/to/static/index.html?host=192.168.1.10&port=8181&path=/core
```

Works whenever the browser can reach the bus (same machine as OVOS, or LAN).
No server required.

### Mode 2 — service (`ovos-busmon`)

Install and run the FastAPI service.
It connects **server-side** to the bus via `ovos-bus-client` and serves:

| Endpoint | Description |
|---|---|
| `GET /` | The same static UI (auto-detected transport: SSE instead of WS) |
| `GET /api/status` | Service health, buffer stats, bus coordinates |
| `GET /api/messages` | Ring buffer contents (`?since_id=N&limit=M`) |
| `GET /api/stream` | SSE live tail |
| `POST /api/send` | Inject a message onto the bus |
| `GET /api/export` | JSONL download of the full capture buffer |

The UI auto-detects which transport to use:
- served from `http://` / `https://` → SSE + REST (Mode 2)
- opened as `file://` or from a static host → direct WebSocket (Mode 1)

## Installation

```bash
pip install ovos-busmon
```

Or from source:

```bash
git clone https://github.com/TigreGotico/ovos-busmon
cd ovos-busmon
pip install -e .[dev]
```

## Running the service

```bash
ovos-busmon
# Listens on http://127.0.0.1:8005 by default
```

### Configuration

All settings via environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `OVOS_BUS_HOST` | `localhost` | OVOS messagebus host |
| `OVOS_BUS_PORT` | `8181` | OVOS messagebus port |
| `BUSMON_HOST` | `127.0.0.1` | Address to bind the HTTP service |
| `BUSMON_PORT` | `8005` | Port to bind the HTTP service |
| `BUSMON_USERNAME` | `ovos` | HTTP Basic auth username |
| `BUSMON_PASSWORD` | `ovos` | HTTP Basic auth password |
| `BUFFER_SIZE` | `2000` | Ring buffer capacity (messages) |

### Docker

```bash
docker compose up --build
```

The compose file binds the service to `127.0.0.1:8005` only (localhost).
To reach an OVOS bus on the host machine, `OVOS_BUS_HOST=host.docker.internal` is set automatically.

## Message injection

The **Inject** panel is a power tool.
It sends arbitrary messages onto the bus — useful for development and testing.
By default the service binds only to `127.0.0.1`; do not expose it to untrusted networks.

## Features

- Live message stream with expandable, syntax-highlighted JSON
- Filter by message type (glob patterns — e.g. `ovos.*`, `recognizer_loop:*`)
- Full-text search across type / data / context / session
- Filter by session ID, source, destination
- Sort newest-first or oldest-first
- Pause/resume capture
- Export as JSONL or JSON (client-side or via `/api/export`)
- Message injection (type + JSON payload → bus)
- Ring buffer with configurable capacity and `since_id` pagination
- GitHub Pages deployable (Mode 1 — no server needed)

## Development

```bash
pip install -e .[dev]
pytest tests/ -v
```

## Security

ovos-busmon is a local debugging tool.
HTTP Basic auth protects the service endpoint, but credentials are sent in plaintext unless you add TLS.
Keep the default `127.0.0.1` binding.
The injection endpoint gives anyone who can reach it full ability to emit any message on the bus.
Do not expose it to the public internet or run it unattended.

## License

MIT — see [LICENSE](LICENSE).
