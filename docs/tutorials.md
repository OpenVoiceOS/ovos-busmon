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

1. Click **Save offline copy** in the Data panel.
2. Save the file to your disk.
3. Open the saved file in the browser.

The saved file is the same monitor. It runs from a local `file://` address, so
the browser does not block the connection.

## 2. Watch and filter the stream

The default view is a live list of every bus message. A line at the top, the now
line, shows the assistant state, such as *Heard*, *Thinking*, *Speaking*, or a
failure to understand. Each row shows a color dot for the message kind, the
message type, the time, and the routing fields as chips.

![Desktop: the flat live stream](img/flat-stream.png)

![Mobile: the flat live stream](img/flat-stream-mobile.png)

The Filter panel filters the visible rows. A filter hides rows. It does not
delete them from the buffer.

The **quick-filter chips** are the fastest filter. Click one chip to show only
one kind, such as Heard, Intents, Skills, Speech, or Errors. Each chip shows a
live count. Click **All** to clear the chip filter.

The Filter panel also has these fields:

- **Type (glob)**: a glob pattern, for example `ovos.*` or `speak`, matches the
  message type.
- **Search content**: a full-text match across type, data, context and session.
- **More filters**: an exact match on the session_id, source, or destination
  field.
- **Order**: newest first or oldest first.

Click **Clear filters** to reset every filter and the selected chip.

![Desktop: the Speech chip shows only speak messages](img/filter-speak.png)

![Mobile: the Speech chip shows only speak messages](img/filter-speak-mobile.png)

To hold the stream still, click **Pause**. Click it again to resume.

The checkbox **Pause when a message matches the filter** stops the stream at the
first message that matches your filters. Set a filter first. Use this to catch
one message live before it scrolls away.

The monitor keeps a bounded buffer. The default is 5000 messages. Set the size
in **Buffer settings**.

The monitor drops the oldest messages first. The status bar shows the dropped
count.

## 3. Inspect a message and trace an interaction

Click a row to expand it. The row opens the `data`, `context` and `session`
fields as highlighted JSON.

![Desktop: an expanded message with highlighted JSON](img/message-detail.png)

![Mobile: an expanded message with highlighted JSON](img/message-detail-mobile.png)

To read one interaction as a single trace, group the stream by session:

1. Click **Group by session** in the View panel.
2. Find the interaction you want. Each group is one session.
3. Click the group to expand its steps.

This view groups the stream by session id. One interaction reads as one trace:
the utterance, then the pipeline match, then the skill handler, then the speak
output.

Each step carries the same color dot as the flat stream. The dot marks the kind:
Heard, Intent, Skill, Speech, Error, or Other.

![Desktop: Group by session with one expanded trace](img/timeline-view.png)

![Mobile: Group by session with one expanded trace](img/timeline-view-mobile.png)

## 4. Inject a message and use the Chat panel

The **Inject** panel sends a message onto the bus. This is a power tool. A wrong
message can change the state of your device. Use it with care.

1. Open the panel **Inject a message onto the bus**.
2. Set **Message type**, for example `speak`.
3. Set **Payload JSON (data)**.
4. Set **Context JSON (optional)** if you need it.
5. Click **Send message**.

The message goes onto the bus. It comes back through the monitor and shows in
the stream.

![Desktop: the Inject panel sends a speak message](img/inject-panel.png)

![Mobile: the Inject panel sends a speak message](img/inject-panel-mobile.png)

The **Chat** panel sends text to the assistant. Each browser session gets one
stable session id. The id holds across page reloads, so multi-turn context and
converse keep working.

1. Click **Chat** in the toolbar.
2. Type your text in the box.
3. Click **Send**.

The reply shows as a bubble in the Chat panel. The full pipeline still flows
through the stream, where you can watch each step.

![Desktop: the Chat panel and the matching bus traffic](img/chat-panel.png)

![Mobile: the Chat panel and the matching bus traffic](img/chat-panel-mobile.png)

The Inject panel and the Chat panel need service mode. They post to the
`/api/send` and `/api/chat` endpoints. See the [usage guide](usage.md) for the
API.

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
