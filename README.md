# ovos-busmon

Live monitor, capture, and injection tool for the [OpenVoiceOS](https://openvoiceos.org) messagebus.
Stream every bus message to a browser, filter by type (glob), inspect payloads, export captures as JSONL, and inject messages directly from the UI.

![timeline view tracing one interaction](docs/img/timeline-view.png)

See [docs/usage.md](docs/usage.md) for a full walkthrough with screenshots.

## Debug your OVOS device from a URL

The monitor UI is a single static page. Hosted on GitHub Pages, anyone can open
the URL on a laptop that can reach an OVOS device and connect to its messagebus
immediately — no install, no server: the page opens a WebSocket straight to
`ws://localhost:8181/core` (host/port configurable in the connection panel or
via `?host=&port=` query parameters).

Browser note: Chromium-based browsers allow a `ws://localhost` connection from
an `https://` page (localhost is a trustworthy origin); Safari and some Firefox
versions block it. If the connection is refused, use the **Download standalone
HTML** button in the UI and open the saved file locally — identical
functionality, no restrictions.

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
| `POST /api/chat` | Send a text utterance as a real client would (chat panel) |
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
git clone https://github.com/OpenVoiceOS/ovos-busmon
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

- Live message stream with expandable, syntax-highlighted JSON (vendored highlighter — fully offline, no CDN)
- Timeline view: group the stream by session into expandable per-interaction traces with category badges
- Chat panel: converse with the assistant in text with a stable session id (multi-turn/converse works) while watching the bus handle each turn
- Filter by message type (glob patterns — e.g. `ovos.*`, `recognizer_loop:*`)
- Full-text search across type / data / context / session
- Filter by session ID, source, destination
- Sort newest-first or oldest-first
- Pause/resume capture, plus auto-pause on filter match
- Bounded client-side buffer (configurable, dropped-count visible)
- Export as JSONL or JSON (client-side or via `/api/export`)
- Message injection (type + JSON `data` + optional JSON `context` → bus)
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

## Related projects

- [ovos-messagebus](https://github.com/OpenVoiceOS/ovos-messagebus) — the bus server this tool monitors
- [ovos-bus-client](https://github.com/OpenVoiceOS/ovos-bus-client) — the client library used in service mode
- [ovos-core](https://github.com/OpenVoiceOS/ovos-core) — the intent pipeline whose traffic you'll be tracing
- [hivemind-core](https://github.com/JarbasHiveMind/hivemind-core) — protected remote access to a bus, busmon works there too

## License

MIT — see [LICENSE](LICENSE).

## Credits

Developed by [TigreGotico](https://tigregotico.pt) for [OpenVoiceOS](https://openvoiceos.org).

Funded by [NGI0 Commons Fund](https://nlnet.nl/project/OpenVoiceOS) / [NLnet](https://nlnet.nl)
under grant agreement No [101135429](https://cordis.europa.eu/project/id/101135429),
through the European Commission's [Next Generation Internet](https://ngi.eu) programme.
