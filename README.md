# ovos-busmon

Live monitor, capture, and injection tool for the [OpenVoiceOS](https://openvoiceos.org) messagebus.
Stream every bus message to a browser, filter by kind, inspect payloads,
export captures as JSONL, and inject messages from the UI.

![Group by session tracing one interaction](docs/img/timeline-view.png)

See the [docs](docs/index.md) for a full walkthrough with screenshots. Start
with the [tutorials](docs/tutorials.md).

## Debug your OVOS device from a URL

The monitor UI is a single static page. Host it on GitHub Pages, and anyone with
a laptop that can reach an OVOS device connects to its messagebus at once. No
install, no server: the page opens a WebSocket straight to
`ws://localhost:8181/core`. Set the host and port in the connection panel or
with the `?host=&port=` query parameters.

Browser note: Chromium browsers allow a `ws://localhost` connection from an
`https://` page, because localhost is a trustworthy origin. Safari and some
Firefox versions block it. If the connection is refused, click **Save offline
copy** in the UI and open the saved file locally. It has the same functions and
no restrictions.

## Two transport modes, one UI

### Mode 1: fully in-browser (zero server)

Open `static/index.html` directly, or deploy it to GitHub Pages.
The page opens a WebSocket **directly to the OVOS messagebus** (`ws://localhost:8181/core` by default).
Set the host, port, and path in the connection panel or with query parameters:

```
file:///path/to/static/index.html?host=192.168.1.10&port=8181&path=/core
```

This works whenever the browser can reach the bus, on the same machine as OVOS
or on a LAN. No server is required.

### Mode 2: service (`ovos-busmon`)

Install and run the FastAPI service.
It connects **server-side** to the bus through `ovos-bus-client` and serves:

| Endpoint | Description |
|---|---|
| `GET /` | The same static UI (auto-detected transport: SSE instead of WS) |
| `GET /api/status` | Service health, buffer stats, bus coordinates |
| `GET /api/messages` | Ring buffer contents (`?since_id=N&limit=M`) |
| `GET /api/stream` | SSE live tail |
| `POST /api/send` | Inject a message onto the bus |
| `POST /api/chat` | Send a text utterance as a real client would (chat panel) |
| `GET /api/export` | JSONL download of the full capture buffer |

The UI auto-detects the transport:
- served from `http://` or `https://`: SSE and REST (Mode 2)
- opened as `file://` or from a static host: direct WebSocket (Mode 1)

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

Set every option through environment variables, or through a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `OVOS_BUS_HOST` | `localhost` | OVOS messagebus host |
| `OVOS_BUS_PORT` | `8181` | OVOS messagebus port |
| `BUSMON_HOST` | `127.0.0.1` | Address to bind the HTTP service |
| `BUSMON_PORT` | `8005` | Port to bind the HTTP service |
| `BUSMON_TOKEN` | (empty) | Shared-secret token. When set, the API needs it |
| `BUSMON_USERNAME` | (empty) | HTTP Basic auth username |
| `BUSMON_PASSWORD` | (empty) | HTTP Basic auth password |
| `BUFFER_SIZE` | `2000` | Ring buffer capacity (messages) |

Authentication is off until you set `BUSMON_TOKEN`, or `BUSMON_USERNAME` and
`BUSMON_PASSWORD`. There are no default credentials.

### Docker

```bash
docker compose up --build
```

The compose file binds the service to `127.0.0.1:8005` only (localhost).
To reach an OVOS bus on the host machine, it sets `OVOS_BUS_HOST=host.docker.internal` automatically.

## Message injection

The **Inject** panel is a power tool.
It sends arbitrary messages onto the bus, which helps with development and testing.
The service binds only to `127.0.0.1` by default. Do not expose it to untrusted networks.

## Features

- Live "now" line: the assistant state (Heard, Thinking, Speaking, or Didn't understand), inferred from the latest traffic
- Live message stream with a per-kind color dot and expandable, highlighted JSON (vendored highlighter, fully offline, no CDN)
- Quick-filter chips with live counts, one each for Heard, Intents, Skills, Speech, or Errors. Errors also get a red edge
- Group by session: group the stream into expandable per-interaction traces
- Chat panel: chat with the assistant in text over one stable session id (multi-turn and converse work) while you watch the bus handle each turn
- Filter by message type (glob patterns, for example `ovos.*` or `recognizer_loop:*`)
- Full-text search across type, data, context and session
- Filter by session id, source, and destination
- Sort newest-first or oldest-first
- Pause and resume capture, plus auto-pause on filter match
- Bounded client-side buffer (configurable, with a visible dropped-count)
- Export as JSONL or JSON (client-side or through `/api/export`)
- Message injection (type, JSON `data`, and optional JSON `context`)
- Ring buffer with configurable capacity and `since_id` pagination
- GitHub Pages deployable (Mode 1, no server needed)

## Development

```bash
pip install -e .[dev]
pytest tests/ -v
```

## Security

ovos-busmon is a local debugging tool. It can inject any message onto the bus,
so an open bind beyond loopback is a remote-control hole.

Authentication is off by default and is meant for loopback use. There are no
default credentials. To use the service beyond loopback, set `BUSMON_TOKEN`
(recommended), or set `BUSMON_USERNAME` and `BUSMON_PASSWORD`. The service
refuses to start on a non-loopback host when no authentication is set.

A token travels as `?token=` on the URL or as an `Authorization: Bearer` header.
The `?token=` form lets the live UI carry the token on its SSE stream, which
HTTP Basic cannot. HTTP Basic auth sends credentials in plaintext unless you add
TLS. Keep the default `127.0.0.1` bind for local use, and do not expose the
service to the public internet.

## Related projects

- [ovos-messagebus](https://github.com/OpenVoiceOS/ovos-messagebus): the bus server this tool monitors
- [ovos-bus-client](https://github.com/OpenVoiceOS/ovos-bus-client): the client library used in service mode
- [ovos-core](https://github.com/OpenVoiceOS/ovos-core): the intent pipeline whose traffic you trace
- [hivemind-core](https://github.com/JarbasHiveMind/hivemind-core): protected remote access to a bus, where busmon also works

## License

MIT. See [LICENSE](LICENSE).

## Credits

Developed by [TigreGotico](https://tigregotico.pt) for [OpenVoiceOS](https://openvoiceos.org).

Funded by [NGI0 Commons Fund](https://nlnet.nl/project/OpenVoiceOS) / [NLnet](https://nlnet.nl)
under grant agreement No [101135429](https://cordis.europa.eu/project/id/101135429),
through the European Commission's [Next Generation Internet](https://ngi.eu) programme.
