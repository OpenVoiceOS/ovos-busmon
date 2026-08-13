# Tutorials

These tutorials show each task step by step. Start at the top and work down.
Every task builds on the one before it.

`ovos-busmon` shows every message on the OVOS messagebus in a web page. The page
is one static file. You can open it from a web address, from a local file, or
from the `ovos-busmon` service.

See the [README](../README.md) for the two transport modes.

## 1. Connect to the bus

The monitor opens a WebSocket to your OVOS device. The device runs the
messagebus on port `8181` at path `/core`.

1. Open the monitor page in a browser.
2. Open the panel **Direct WebSocket connection settings**.
3. Set **Host** to your device address. The default is `localhost`.
4. Set **Port** to `8181` and **Path** to `/core`.
5. Click **Connect**.

You can also set the target in the web address. Add `?host=`, `?port=`, and
`?path=` to the URL:

```
file:///path/to/static/index.html?host=192.168.1.10&port=8181&path=/core
```

The stream starts when the browser reaches the bus. This works on the OVOS
machine or on a LAN.

### If the connection fails from an https page

A browser can block a `ws://localhost` connection from an `https://` page.
Chromium browsers allow it. Safari and some Firefox versions block it.

To work around this block, do the following:

1. Open the **Tools** menu and click **Save offline copy**.
2. Save the file to your disk.
3. Open the saved file in the browser.

The saved file is the same monitor. It runs from a local `file://` address, so
the browser does not block the connection.

## 2. Watch and filter the stream

The default view is a dense log, one row per bus message. A line at the top,
the now line, shows the assistant state, such as *Heard*, *Thinking*,
*Speaking*, or a failure to understand.

Each row shows the time, the message type, a short detail, the session, and
the source and destination. A color on the left edge of the row marks the
category. An error row gets a red edge.

![Desktop: the dense DevTools-style log](img/flat-stream.png)

![Mobile: the dense DevTools-style log](img/flat-stream-mobile.png)

### Firehose control

A real device bus bursts with high-frequency plumbing: sensor polling, sync
heartbeats, enclosure animation, mic level updates, and IPC chatter. The log
mutes these message types by default, so the signal does not drown.

Click **Show noise** to reveal them. The button shows a live count. Click it
again to mute them back.

When several rows in a row share the same message type, the log coalesces
them into one row with a **×N** count next to the type. This keeps a burst of
identical messages readable as a single line.

### Filtering the visible rows

A filter hides rows. It does not delete them from the buffer.

The **category chips** are the fastest filter: all, heard, intents, skills,
speech, and errors. Click one chip to show only that category. Each chip shows
a live count. Click **all** to clear the chip filter.

The filter bar also has these fields:

- **Type (glob)**: a glob pattern, for example `ovos.*` or `speak`, matches the
  message type.
- **Search content**: a full-text match across type, data, context and session.
- **Session**, **Source**, **Destination**: a match on that field.
- **Order**: newest first or oldest first.

Click **Clear** to reset every filter and the selected chip.

Every value shown in a row is also a filter switch. Click a **type** to watch
only that topic. Click a **session** to inspect that session.

Click a **source** or **destination** to filter that route. Active filters
show as removable tags above the log.

![Desktop: a chip filters the log to speak messages](img/filter-speak.png)

![Mobile: a chip filters the log to speak messages](img/filter-speak-mobile.png)

To hold the stream still, click **Pause**. Click it again to resume.

Open the **Tools** menu for more controls. The checkbox **Pause on filter
match** stops the stream at the first message that matches your filters. Set a
filter first. Use this to catch one message live before it scrolls away.

The monitor keeps a bounded buffer. The default is 5000 messages. Set the size
in the **Tools** menu.

The monitor drops the oldest messages first. The status bar shows the dropped
count.

## 3. Inspect a message and trace an interaction

Click a row to expand it inline. The row opens the `data`, `context`, and
`session` fields as highlighted JSON, with a **Copy JSON** button for the
whole message.

While a row is open, the log freezes. New traffic queues instead of pushing
the open row out of view. Collapse the row to resume the live view. The
queued traffic then renders.

![Desktop: an expanded row with highlighted JSON](img/message-detail.png)

![Mobile: an expanded row with highlighted JSON](img/message-detail-mobile.png)

To read one interaction as a single trace, group the stream by session:

1. Click **Group by session** in the toolbar.
2. Find the interaction you want. Each group is one session.
3. Click the group to expand its steps.

This view groups the stream by session id. One interaction reads as one trace:
the utterance, then the pipeline match (the pipeline is the ordered list of
intent-matcher ids the core tries), then the skill handler, then the speak
output.

Each step carries the same category color as the log. The color marks the
kind: heard, intent, skill, speech, error, or other.

![Desktop: Group by session with one expanded trace](img/timeline-view.png)

![Mobile: Group by session with one expanded trace](img/timeline-view-mobile.png)

## 4. Inject a message, replay traffic, and chat

### Inject a message

The **Inject** panel sends a message onto the bus. It works in both transport
modes: over the WebSocket in direct mode, or through the `/api/send` endpoint
in service mode. This is a power tool. A wrong message can change the state of
your device. Use it with care.

1. Open the panel **Inject a message onto the bus**.
2. Set **Message type**, for example `speak`.
3. Set **Payload JSON (data)**.
4. Set **Context JSON (optional)** if you need it.
5. Click **Send message**.

The message goes onto the bus. It comes back through the monitor and shows in
the log.

To fill a common type, pick one from the **Preset** dropdown first.

![Desktop: the Inject panel and the Session editor](img/inject-panel.png)

![Mobile: the Inject panel and the Session editor](img/inject-panel-mobile.png)

### Replay a captured message

Resend and Edit & send also work in both transport modes. Expand a row in the
log and use one of these:

1. **Resend**: send that exact message again, with its original `data` and
   `context`.
2. **Edit & send**: load it into the Inject panel, then edit and send.

### Build a Session

To send under a specific session, use the **Session** panel. An OVOS session
travels in each message. Build one here:

1. Set the fields you need, such as **lang** or **site_id**.
2. To copy a session from the log, click a `session=` value in a row.
3. For an inject, check **attach the Session below**.

### Chat with the assistant

Chat needs service mode. If you followed section 1 with a direct WebSocket
connection, start the `ovos-busmon` service first and open its page instead
(see the [README](../README.md) for how to run the service), then come back
to this step.

The **Chat** panel sends text to the assistant. Each browser session gets one
stable session id. The id holds across page reloads, so multi-turn context and
converse keep working.

1. Click **Chat** in the toolbar.
2. Type your text in the box.
3. Click **Send**.

The reply shows as a bubble in the Chat panel. The full pipeline still flows
through the log, where you can watch each step.

When the **Session** panel is filled, chat sends under that session. Under each
turn, click **trace** to see the bus events that turn produced.

Chat posts to the `/api/chat` endpoint, which emits `recognizer_loop:utterance`
shaped exactly like a real text client. See the [usage guide](usage.md) for the
API.

![Desktop: the Chat panel and the matching bus traffic](img/chat-panel.png)

![Mobile: the Chat panel and the matching bus traffic](img/chat-panel-mobile.png)

## 5. Export a capture

The toolbar exports the buffer to a file. Pick one of three formats:

- **Export JSONL**: one JSON message per line.
- **Export JSON**: one JSON array of every message.
- **Save offline copy**: the whole monitor as a local file, with the messages
  inside it.

In service mode, **Export JSONL** downloads the full server buffer from the
`/api/export` endpoint.

---
[Home](index.md) · [Usage →](usage.md)
