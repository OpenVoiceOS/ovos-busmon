# Using ovos-busmon

`ovos-busmon` streams every message on the OVOS messagebus to a browser. There
you can filter and inspect the log, trace an interaction, inject a message, and
chat with the assistant. This page is a reference for each part of the UI. For
installation and the transport modes, see the [README](../README.md). For a
step-by-step walkthrough, see the [tutorials](tutorials.md).

## The now line

A single line at the top says what the assistant is doing right now. It reads
the latest meaningful traffic and shows one of six states: *Live* (idle,
waiting for traffic), *Heard* (an utterance came in), *Thinking* (the pipeline
is matching an intent), *Working* (a skill handler is running), *Speaking*
(output goes out), or *Didn't understand* (an error). Use it to see the
assistant's state at a glance without reading the stream.

## The live log

The default view is a dense, DevTools-style log: one monospace row per bus
message, with the time, type, a short detail, the session, and the
source-to-destination route. A color on the left edge of the row marks the
category, and an **error** row gets a red edge instead.

Click a row to expand its `data`, `context`, and `session` payloads as
highlighted JSON, inline below the row. **Copy JSON** copies the whole
message. While a row is expanded, the log freezes: new traffic queues instead
of scrolling the row away, and rendering resumes when you collapse it.

![Desktop: the dense log](img/flat-stream.png)

![Mobile: the dense log](img/flat-stream-mobile.png)

![Desktop: an expanded row with highlighted JSON](img/message-detail.png)

![Mobile: an expanded row with highlighted JSON](img/message-detail-mobile.png)

### Firehose control (noise)

High-frequency plumbing, such as sensor polling, sync heartbeats, enclosure
animation, mic level updates, and IPC traffic, is muted by default so it does
not drown the messages you care about. The **Show noise** button reveals it,
shows a live count, and toggles back to hide it again.

Consecutive rows that are true duplicates coalesce into one row with a **×N**
count next to the type, so a burst reads as a single line instead of a wall of
duplicates. Two rows coalesce only when the type, the session, and the data all
match. Rows with a different session or different data stay separate, so the log
never hides a distinct message behind a count.

### Filtering

The filter bar filters the visible log. It does not discard anything from the
capture buffer.

- **Category chips**: all, heard, intents, skills, speech, errors. Each
  chip shows a live count. **all** clears the chip filter.
- **Type (glob)**: glob patterns, for example `ovos.*`, `recognizer_loop:*`, or
  `speak`.
- **Search content**: full-text across type, data, context and session.
- **Session**, **Source**, **Destination**: match that field.
- **Order**: newest first (the default) or oldest first.
- **Clear**: reset every filter and the selected chip.

Click-to-filter works on every row: click a **type** to watch that topic,
a **session** to inspect it, or a **source** or **destination** to filter that
route. Active filters render as removable tags above the log.

![Desktop: a chip filters the log to speak messages](img/filter-speak.png)

![Mobile: a chip filters the log to speak messages](img/filter-speak-mobile.png)

### Buffer, pause, and the Tools menu

The client keeps a bounded buffer. The default is 5000 messages, and you set
the size from the **Tools** menu. The client drops the oldest messages first,
and the status bar shows how many it dropped.

**Pause** stops ingestion. In the **Tools** menu, **Pause on filter match**
stops the log the instant an incoming message matches the active filters, to
catch one specific message live without losing it to scrollback.

The **Tools** menu also holds **Export JSONL**, **Export JSON**, **Save
offline copy**, and **Clear buffer**.

#### Two buffers, not one

There are two independent caps on how much traffic the monitor holds.

- **Client buffer.** Set from the **Tools** menu. Default 5000 messages. It
  caps what the browser renders and exports in direct-WebSocket mode (Mode
  1).
- **Server ring buffer.** Set with the `BUFFER_SIZE` environment variable.
  Default 2000 messages. It backs `/api/messages`, `/api/export`, and
  `/api/status` in service mode (Mode 2).

The two caps do not share a value. See the [README configuration
table](../README.md#configuration) for the server-side variable.

### Keyboard shortcuts

The shortcuts work only when focus is on the page, not inside a text field.

| Key | Action |
|---|---|
| `/` | Focus the search field |
| `p` | Pause or resume the log |
| `g` | Toggle group by session |

### Theme

The **◐** button at `#theme-toggle` switches between light and dark theme.
The choice persists in the browser's local storage.

## Group by session

**Group by session** groups the flat stream by session id. When a session id is
absent, it falls back to an utterance-correlation id in `context`. One
interaction then reads as a single expandable trace: utterance, then pipeline
match, then skill handler, then speak output. Each step carries the same color
dot as the flat stream: Heard, Intent, Skill, Speech, Error, or Other.

![Desktop: Group by session with an expanded trace](img/timeline-view.png)

![Mobile: Group by session with an expanded trace](img/timeline-view-mobile.png)

## Chat panel

The **Chat** button opens a side panel. There you chat with the assistant in
text, straight from the monitor. Each browser session gets one stable session
id. The panel shows the id at the bottom and keeps it across reloads, so
multi-turn context and converse keep working.

Replies that belong to that session (`ovos.utterance.speak` or `speak`) render
as bubbles. Everything else keeps flowing through the normal stream, where you
watch the full pipeline handle your utterance.

When the [Session editor](#the-session-editor) is filled, chat sends every turn
under that session instead of the default id. Set a `lang` or a `site_id` there
to converse as a different device.

Under each turn, a **trace** toggle shows the bus events that turn produced,
built from captured traffic. Use it to see the pipeline handle one utterance
without leaving the chat.

Chat needs service mode. It posts to the `/api/chat` endpoint, which emits
`recognizer_loop:utterance` shaped exactly like a real text client. The endpoint
also accepts an optional `session` object, which it honors as declared.

![Desktop: the Chat panel and the matching bus traffic](img/chat-panel.png)

![Mobile: the Chat panel and the matching bus traffic](img/chat-panel-mobile.png)

## Injecting messages

The **Inject** panel sends an arbitrary message onto the bus: a type, a `data`
JSON, and an optional `context` JSON. Inject works in both transport modes. In
service mode, it posts to the `/api/send` endpoint, which validates the
message and emits it through the bus client. In direct WebSocket mode, it
sends the message straight over the WebSocket. Either way, the message comes
back in the stream through the monitor's own listener. This gives you a full
bus REPL for reproducing bugs.

A **Preset** dropdown fills a common message type, such as `speak` or
`recognizer_loop:utterance`, with a skeleton payload. You then edit and send.

You can also replay from the log. Expand any row and use:

- **Resend**: re-inject that exact message, with its original `data` and
  `context`, onto the bus.
- **Edit & send**: load that message into the Inject panel, so you tweak it
  before sending.

![Desktop: the Inject panel and the Session editor](img/inject-panel.png)

![Mobile: the Inject panel and the Session editor](img/inject-panel-mobile.png)

## The Session editor

An OVOS session is stateless. The client declares it in each message, inside
`context["session"]`. The **Session** panel builds one, so you can test how the
core behaves under a given session.

The typed fields are `session_id`, `lang`, `site_id`, `system_unit`, and
`pipeline` (a comma-separated list of matcher ids). An **Advanced** box merges
raw session JSON for any other field. To seed the editor from live traffic,
click a `session=` value in a row, or use **Load session** on an expanded row.

The **Session** applies in two places:

- The Inject panel attaches it when you check **attach the Session below**.
- The Chat panel sends every turn under it (see below).

## HTTP API

The API endpoints need authentication only when you configure it. Set
`BUSMON_TOKEN`, or set `BUSMON_USERNAME` and `BUSMON_PASSWORD`. With no
credentials set, the endpoints are open, and the service allows this on a
loopback bind only. See the [README](../README.md) for the rules.

| Endpoint | Description |
|---|---|
| `GET /api/status` | Service health, buffer stats, bus coordinates |
| `GET /api/messages?since_id=N&limit=M` | Ring buffer contents |
| `GET /api/stream` | SSE live tail |
| `POST /api/send` | Inject `{type, data, context}` onto the bus |
| `POST /api/chat` | Send `{utterance, lang, session_id}` as a text utterance |
| `GET /api/export` | JSONL download of the full capture buffer |

A token travels as `?token=` on the URL or as an `Authorization: Bearer` header.
The `?token=` form lets the SSE stream carry the token, which HTTP Basic cannot.

---
[← Tutorials](tutorials.md) · [Home](index.md) · [Troubleshooting →](troubleshooting.md)
