# Troubleshooting

This page lists the common problems. Each entry gives the symptom, the cause,
and the fix.

## The connection is refused from an https page

**Symptom.** You open the monitor from an `https://` page. The stream never
starts. The browser reports a blocked or refused WebSocket.

**Cause.** A browser can block a `ws://localhost` connection from an `https://`
page. Chromium browsers allow it. Safari and some Firefox versions block it.

**Fix.** Use the offline copy:

1. Open the **Tools** menu and click **Save offline copy**.
2. Save the file to your disk.
3. Open the saved file in the browser.

The saved file runs from a local `file://` address. The browser does not block
the connection.

## The service refuses to start on a non-loopback host

**Symptom.** You start `ovos-busmon` with `BUSMON_HOST` set to a LAN or public
address. The service exits at once. It prints an error about a non-loopback
host without authentication.

**Cause.** The monitor can inject bus messages. An open bind beyond loopback is
a remote-control hole. The service refuses this bind when no authentication is
set.

**Fix.** Choose one of two options:

- Set `BUSMON_TOKEN` to a secret value. You can also set `BUSMON_USERNAME` and
  `BUSMON_PASSWORD`.
- Bind a loopback address. Set `BUSMON_HOST` to `127.0.0.1`, `localhost`, or
  `::1`.

## The API returns 401 Unauthorized

**Symptom.** A request to an `/api/` endpoint returns `401 Unauthorized`.

**Cause.** The service has a token or a username and password set. The request
did not carry valid credentials.

**Fix.** Send the credentials with the request:

- For a token, add `?token=YOUR_TOKEN` to the URL. You can also send the header
  `Authorization: Bearer YOUR_TOKEN`.
- For a username and password, send HTTP Basic auth.

The monitor page reads `?token=` from its own URL one time. It stores the token
and sends it on every later request. Open the page with `?token=YOUR_TOKEN` once
to authenticate it.

## Nothing streams

**Symptom.** The monitor connects, but no messages appear.

**Cause.** The bus host or port is wrong, or the messagebus is not running.

**Fix.** Check each item:

1. Confirm the messagebus runs on your device. The default port is `8181`.
2. Check the **Host**, **Port**, and **Path** in the connection panel. The
   defaults are `localhost`, `8181`, and `/core`.
3. In service mode, check `OVOS_BUS_HOST` and `OVOS_BUS_PORT`.

## The stream looks empty or too quiet

**Symptom.** The monitor connects, but few or no rows appear, even though the
device is active.

**Cause.** High-frequency plumbing, such as sensor polling, sync heartbeats,
enclosure animation, and IPC traffic, is muted by default. It does not appear
in the log or in the category chip counts.

**Fix.** Click **Show noise** in the toolbar. It shows a live count of the
muted messages. Click it again to mute them back.

## The stream looks idle

**Symptom.** The monitor connects and shows no error, but the stream stays
still.

**Cause.** The bus carries no traffic. A device with no active skill or no voice
input can stay quiet.

**Fix.** Make the device do something. Speak to it, or use the Chat panel to
send a text utterance. New messages then appear in the stream.

Confirm that **Pause** is off. A paused monitor shows no new messages. The
button reads **Resume** when the monitor is paused.

---
[← Usage](usage.md) · [Home](index.md)
