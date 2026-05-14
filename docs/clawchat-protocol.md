# Protocol v2

This document describes the final wire contract implemented in this repository.

## Core rules

- `message.received` has been removed. Use `message.reply`.
- `message_mode` lives at `payload.message_mode`.
- `client_message_id` does not exist.
- `created_at`, `updated_at`, and `received_at` do not exist.
- **Routing is driven by `chat_id`.** Every business event carries an envelope-top-level `chat_id`; the server calls `chat.Resolver.GetInfoFromChatID(chat_id)` to look up the chat's `{type, members}`, stamps `chat_type` on the downlink, and fans out the frame to each member *except the sender* (one Kafka produce per recipient, keyed by recipient user id). Chats cover both DMs (2 members, wire `chat_type="direct"`) and groups (N members, wire `chat_type="group"`) — there is no separate "direct" vs "group" routing path.
- **`chat_type` is server-stamped on downlinks only.** Wire values: `"direct"` (DM) or `"group"`. Uplink frames MUST omit `chat_type`; any client-supplied value is ignored and overwritten. Adapters reject any other downlink value.
- Envelope-top-level `to` is preserved end-to-end for UI context (e.g. which conversation row to render the message under) but is NOT used by the server for routing. Clients MAY omit it.
- Routed server-originated business events use envelope-top-level `sender`.
- Transport authentication is handled by the WebSocket `Authorization: Bearer <token>` header and the `bearer.<token>` subprotocol. JSON auth handshake events are not part of this adapter contract.
- `X-Device-Id` identifies the client device for multi-device delivery.
- All clients use device-level replay.
- `to.type` and `sender.type` only allow `direct` or `group`.
- `sender` always identifies a user: `sender.type="direct"`, `sender.id = <user_id>`. Any client-supplied `sender` on uplink is discarded; the server stamps it from the authenticated identity.
- Client-originated `message.send` and `message.reply` do not send top-level `sender`.
- Server-originated `message.send` and `message.reply` fill top-level `sender`.
- Uplink `message.send` / `message.reply` payloads omit `message.streaming`. They SHOULD omit `message_id` too; when present, the server preserves it verbatim (used by streaming producers to finalize a stream — the finalize reply carries the stream's id so the offline store collapses both into a single row).
- Downlink `message.send` / `message.reply` payloads include payload-level `message_id` plus `message.streaming`.
- **Streaming lifecycle events (`message.created` / `message.add` / `message.done` / `message.failed`) use a flat payload**: `fragments`, `streaming`, `sequence`, `mutation`, `added_at`, `completed_at` live at `payload` top level — NOT nested in `payload.message.body`. This differs from `message.send` / `message.reply`, which carry a materialized `message{body, context, streaming}` object. Online producers should finish the stream with `message.done`; replay/storage layers can materialize completed streams as `message.reply` for missed-message replay.
- On `message.add`, every text fragment MUST carry both `text` (cumulative so far) and `delta` (the new piece added this round). Downstream consumers can rebuild the running text from either — `text` is idempotent on replay, `delta` is cheap to apply incrementally.
- Canonical business events never use payload-level `to` / `sender`.
- Canonical message objects never use nested `message.chat` or `message.sender`.
- `message_id` appears only at payload top level on events about one concrete materialized message.
- Device replay sends missed messages as the original downlink envelopes in cursor order after the WebSocket session opens; it does not wrap them in batch envelopes and it does not require receiver-side ack frames. The server advances the device replay cursor only after a successful WebSocket write. Live realtime writes advance the cursor only when no older replay record would be skipped.

## Event taxonomy

| Event | Direction | Envelope `to` | Envelope `sender` |
| --- | --- | --- | --- |
| `message.send` | Client ↔ Server | yes | client: no / server: yes |
| `message.ack` | Server → Client | yes | no |
| `message.reply` | Client ↔ Server | yes | client: no / server: yes |
| `message.created` | Client ↔ Server | yes | client: no / server: yes |
| `message.add` | Client ↔ Server | yes | client: no / server: yes |
| `message.done` | Client ↔ Server | yes | client: no / server: yes |
| `message.failed` | Client ↔ Server | yes | client: no / server: yes |
| `typing.update` | Either | yes | yes (server-injected) |
| `ping` | Either | no | no |
| `pong` | Either | no | no |

## Envelope shape

Every frame on the wire is a JSON object with a uniform top level:

| Field | Type | Presence | Notes |
|-------|------|----------|-------|
| `version` | string | always | Currently `"2"`. |
| `event` | string | always | Event name (see taxonomy). |
| `trace_id` | string | always | Client-chosen on uplink; echoed by server on the matching response. |
| `emitted_at` | int64 | always | Milliseconds since epoch. Server restamps on `typing.update` and streaming events. |
| `chat_id` | string | business events | Drives routing. See *Canonical routing objects*. |
| `chat_type` | string | server-stamped downlinks | `"direct"` or `"group"`. Clients MUST omit on uplink. |
| `to` | object | business events | UI context only; not used for routing. MAY be omitted. |
| `sender` | object | server downlinks | Injected by the server from the authenticated identity. |
| `payload` | object | always | Event-specific body; opaque to envelope-level validators. |

## Canonical routing objects

### `to`

```json
{ "id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y", "type": "direct" }
```

### `sender`

```json
{
  "id": "agent-01HVB6U7K8L9M0N1P2Q3R4S5T6",
  "type": "direct",
  "nick_name": "Clawling Assistant"
}
```

### `reply_preview`

Nested inside `message.context.reply` on reply envelopes. It is a tiny
snapshot of the message being replied to, enough for a UI to render an
inline quote without another round-trip.

```json
{
  "id": "user-alice",
  "nick_name": "Alice",
  "fragments": [{ "kind": "text", "text": "hi" }]
}
```

`id` is the user id of the original message's sender. `fragments` is a
trimmed preview of the original body (not necessarily the full content).

### `chat_id`

Top-level string. Drives routing — the hub calls
`chat.Resolver.GetInfoFromChatID(chat_id)` → `{type, members}`, stamps
`chat_type` on the downlink, excludes the sender, and produces one Kafka
record per remaining member.

```json
"chat_id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y"
```

DMs and group chats are not distinguished at the protocol layer — both are
"a chat with a member set".

### `chat_type`

Server-stamped on every downlink. Wire values: `"direct"` or `"group"`.
Uplinks MUST omit it. Clients should render 1:1 vs group conversations
based on `chat_type`; the member count is an implementation detail of
the upstream service.

## Fragments

`fragments` is an ordered list of heterogeneous fragments. Each fragment
carries a `kind` discriminator; only the fields relevant to that kind are
populated (everything else is omitted). Unknown kinds MUST be preserved
by intermediaries and rendered as "unsupported content" by clients.

TypeScript union form (authoritative):

```ts
type Fragment =
  | { kind: "text",    text: string, delta?: string }
  | { kind: "mention", user_id?: string, display?: string }
  | { kind: "image",   url: string, name?: string, mime?: string, size?: number,
                       width?: number, height?: number }
  | { kind: "file",    url: string, name?: string, mime?: string, size?: number }
  | { kind: "audio",   url: string, name?: string, mime?: string, size?: number,
                       duration?: number }
  | { kind: "video",   url: string, name?: string, mime?: string, size?: number,
                       width?: number, height?: number, duration?: number };
```

**Unit conventions**:

- `width`, `height` are **pixels**
- `duration` is **milliseconds**
- `size` is **bytes**

### `kind: "text"`

```json
{ "kind": "text", "text": "Hello" }
```

On `message.add` frames, the text fragment additionally carries `delta`:

```json
{ "kind": "text", "text": "Hello, world", "delta": ", world" }
```

- `text` is the CUMULATIVE content after this round.
- `delta` is the NEW piece appended this round.

The invariant `text_prev + delta == text` holds across consecutive adds
for the same fragment. `delta` is absent on `message.created`,
`message.done`, and materialized `message.send` / `message.reply`.

### `kind: "mention"`

```json
{ "kind": "mention", "user_id": "user-alice", "display": "Alice" }
```

### `kind: "image"` / `"file"` / `"audio"` / `"video"`

```json
{
  "kind": "image",
  "url": "https://media.example.com/media/01HVB6....png",
  "name": "photo.png",
  "mime": "image/png",
  "size": 12345,
  "width": 1920,
  "height": 1080
}
```

Notes:

- `url` is a directly browser-retrievable URL from the bucket's public
  base. Every upload gets a random ULID-keyed path — the URL itself is
  the only capability.
- Single-file uploads are capped at 20 MB by default.
- Stored objects are auto-deleted after `media.retention_days` (15 by
  default) via a bucket lifecycle rule.

## Message shapes

### Uplink message content

Used inside client-originated `message.send.payload.message` and
`message.reply.payload.message`.

```json
{
  "body": {
    "fragments": [{ "kind": "text", "text": "Hello from the SDK" }]
  },
  "context": { "mentions": [], "reply": null }
}
```

### Materialized downlink message

Used inside server-originated `message.send`, `message.reply`, and the
consolidated `message.reply` emitted at the end of a stream.

```json
{
  "body": { "fragments": [{ "kind": "text", "text": "Hello" }] },
  "context": { "mentions": [], "reply": null },
  "streaming": {
    "status": "static",
    "sequence": 0,
    "mutation_policy": "sealed",
    "started_at": null,
    "completed_at": null
  }
}
```

## Streaming payload shape

Streaming lifecycle events (`message.created` / `message.add` /
`message.done` / `message.failed`) use a **flat** payload — fragments
and streaming metadata live at `payload` top level, NOT inside
`payload.message.body`. Replay/storage layers can convert this flat form
into the materialized `message{body, context, streaming}` shape for
missed-message replay.

### `message.created` payload

Intentionally minimal — it opens the stream and pins the `message_id`
shared by every subsequent event. No content is required.

```json
{ "message_id": "agent-stream-01K..." }
```

MAY additionally carry `message_mode` (e.g. `"thinking"`) if the producer
wants to hint the client's render style before any text arrives.

### `message.add` payload

Carries one increment. Required fields:

| Field | Type | Notes |
|-------|------|-------|
| `message_id` | string | Same id as the stream's `message.created`. |
| `sequence` | int | Monotonic per-stream counter, starting from 0. |
| `mutation` | object | Describes *which* fragment changed and *how* (see below). |
| `fragments` | array | Current cumulative fragment list after applying this mutation. Text fragments MUST include `delta`. |
| `streaming` | object | `{status, sequence, mutation_policy, started_at, completed_at}`. |
| `added_at` | int64 | Milliseconds since epoch. Restamped by the server. |

### `message.done` payload

Closes the stream. The final, fully-merged fragment list is echoed one
last time so consumers that missed earlier frames (or receivers replaying
offline storage) can materialize the message without replaying every
`add`.

| Field | Type | Notes |
|-------|------|-------|
| `message_id` | string | Same id as the stream. |
| `fragments` | array | Final merged fragments (no `delta`). |
| `streaming` | object | `status: "done"`, `sequence` equal to the last `add`, `completed_at` set. |
| `completed_at` | int64 | Milliseconds since epoch. |

### `message.failed` payload

Shape mirrors `message.done` but with `streaming.status="failed"` and no
requirement on `fragments`. Producers SHOULD include a short reason in
`fragments[0].text` for debugging.

### `mutation` object

Describes how the new `fragments` differ from the previous frame's
`fragments`.

| Field | Type | Notes |
|-------|------|-------|
| `type` | string | `"append"` (add to end) — currently the only supported operation. Future: `"replace"`, `"insert"`. |
| `target_fragment_index` | int \| null | Zero-based index of the fragment being mutated. `null` when `type == "append"` and the operation targets a new fragment appended at the end. |

```json
{ "type": "append", "target_fragment_index": null }
```

### `streaming` object

| Field | Type | Notes |
|-------|------|-------|
| `status` | string | `"static"` \| `"streaming"` \| `"done"` \| `"failed"`. |
| `sequence` | int | Mirrors `payload.sequence` on `message.add`; 0 on static / created. |
| `mutation_policy` | string | `"sealed"` (no further mutations) \| `"append_text_only"` \| future policies. |
| `started_at` | int64 \| null | Milliseconds since epoch, set on the first streaming event. |
| `completed_at` | int64 \| null | Milliseconds since epoch, set on `done` / `failed`. |

## Example envelopes

### `message.send`

Client → server normal message:

```json
{
  "version": "2",
  "event": "message.send",
  "trace_id": "trace-01HVB6QY6V8J9VZ7S4A9Q0J8M2",
  "emitted_at": 1776162600000,
  "chat_id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y",
  "to": { "id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y", "type": "direct" },
  "payload": {
    "message_mode": "normal",
    "message": {
      "body": { "fragments": [{ "kind": "text", "text": "hi" }] },
      "context": { "mentions": [], "reply": null }
    }
  }
}
```

Server → each chat member except sender:

```json
{
  "version": "2",
  "event": "message.send",
  "trace_id": "trace-send-downlink-01HVB6S1A2B3C4D5E6F7G8H9J0",
  "emitted_at": 1776162601500,
  "chat_id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y",
  "chat_type": "direct",
  "to": { "id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y", "type": "direct" },
  "sender": { "id": "user-alice", "type": "direct", "nick_name": "Alice" },
  "payload": {
    "message_id": "msg-01HVB6S7K8L9M0N1P2Q3R4S5T6",
    "message_mode": "normal",
    "message": {
      "body": { "fragments": [{ "kind": "text", "text": "hi" }] },
      "context": { "mentions": [], "reply": null },
      "streaming": {
        "status": "static", "sequence": 0, "mutation_policy": "sealed",
        "started_at": null, "completed_at": null
      }
    }
  }
}
```

### `message.ack`

```json
{
  "version": "2",
  "event": "message.ack",
  "trace_id": "trace-ack-01HVB6S1A2B3C4D5E6F7G8H9J0",
  "emitted_at": 1776162601000,
  "chat_id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y",
  "to": { "id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y", "type": "direct" },
  "payload": {
    "message_id": "msg-01HVB6S7K8L9M0N1P2Q3R4S5T6",
    "accepted_at": 1776162601000
  }
}
```

### `message.created`

Intentionally minimal — opens the stream:

```json
{
  "version": "2",
  "event": "message.created",
  "chat_id": "chat-alice",
  "chat_type": "direct",
  "payload": { "message_id": "agent-stream-01K..." }
}
```

### `message.add`

Each delta carries BOTH cumulative `text` and the new `delta`:

```json
{
  "version": "2",
  "event": "message.add",
  "chat_id": "chat-alice",
  "chat_type": "direct",
  "payload": {
    "message_id": "agent-stream-01K...",
    "sequence": 3,
    "mutation": { "type": "append", "target_fragment_index": null },
    "fragments": [
      { "kind": "text", "text": "Hello, world", "delta": ", world" }
    ],
    "streaming": {
      "status": "streaming",
      "sequence": 3,
      "mutation_policy": "append_text_only",
      "started_at": null,
      "completed_at": null
    },
    "added_at": 1776406831114
  }
}
```

### `message.done`

Carries the full merged final fragment list:

```json
{
  "version": "2",
  "event": "message.done",
  "chat_id": "chat-alice",
  "chat_type": "direct",
  "payload": {
    "message_id": "agent-stream-01K...",
    "fragments": [{ "kind": "text", "text": "Hello, world" }],
    "streaming": {
      "status": "done",
      "sequence": 3,
      "mutation_policy": "append_text_only",
      "started_at": null,
      "completed_at": 1776406831120
    },
    "completed_at": 1776406831120
  }
}
```

### `message.reply`

Client → server reply intent:

```json
{
  "version": "2",
  "event": "message.reply",
  "trace_id": "trace-reply-up-01HVB6T1A2B3C4D5E6F7G8H9J0",
  "emitted_at": 1776162601800,
  "chat_id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y",
  "to": { "id": "chat-01HVB6R6XQ9J4S5T6U7V8W9X0Y", "type": "direct" },
  "payload": {
    "message_mode": "normal",
    "message": {
      "body": { "fragments": [{ "kind": "text", "text": "Replying from the client." }] },
      "context": {
        "mentions": [],
        "reply": {
          "reply_to_msg_id": "msg-01HVB6S7K8L9M0N1P2Q3R4S5T6",
          "reply_preview": {
            "id": "user-alice",
            "nick_name": "Alice",
            "fragments": [{ "kind": "text", "text": "Original message" }]
          }
        }
      }
    }
  }
}
```

Replay-materialized completed stream — SAME `message_id` as the
`message.created` / `message.add` / `message.done` sequence, and
optionally quotes the user message that triggered the stream. Online
streaming producers should not send this immediately after `message.done`;
it is the shape replay/storage layers use when a recipient missed the live
stream:

```json
{
  "version": "2",
  "event": "message.reply",
  "chat_id": "chat-alice",
  "chat_type": "direct",
  "payload": {
    "message_id": "agent-stream-01K...",
    "message_mode": "normal",
    "message": {
      "body": { "fragments": [{ "kind": "text", "text": "Hello, world" }] },
      "context": {
        "mentions": [],
        "reply": {
          "reply_to_msg_id": "user-msg-01K...",
          "reply_preview": {
            "id": "user-alice",
            "nick_name": "Alice",
            "fragments": [{ "kind": "text", "text": "hi" }]
          }
        }
      }
    }
  }
}
```

Reusing the stream's `message_id` on the replay materialization lets the
offline store keep one durable completed-stream row.

## Connection Authentication

Every WebSocket session authenticates during the HTTP upgrade. The adapter sends
`Authorization: Bearer <token>`, `X-Device-Id: <stable-device-id>`, and
subprotocols `clawchat.v1` plus `bearer.<token>`. A socket accepted by the
server is immediately ready for business events; the adapter does not send or
wait for JSON auth frames.

## Device Replay

After the WebSocket session opens, the server replays missed messages for the authenticated
`user_id + device_id` by sending the original downlink envelopes in delivery
order:

```
message.send / message.reply / message.created / message.add / message.done ...
```

Device replay does not introduce a receiver-side ack. The server advances
the device cursor only after `WriteMessage` succeeds for that envelope. If
the connection closes before a write succeeds, the same envelope remains
eligible for replay on the next session.

Replay and live delivery share one ordered stream per device. While replay
is catching up, newer messages MUST NOT bypass older missed messages for the
same `user_id + device_id`; they remain in the durable inbox and are sent
when their turn arrives.

Servers MAY apply replay flow control. Typical controls are:

| Control | Meaning |
|---|---|
| `batch_size` | Number of inbox rows loaded per storage query. |
| `send_rate` | Maximum replay writes per second for one device. |
| `max_pending` | Maximum queued-but-not-yet-written replay envelopes for one device. |

The replay cursor is server-side protocol state. Clients should deduplicate
by `payload.message_id` because a server can retry an envelope after a
disconnect or failover.

## Typing + streaming reply pattern

Streaming responses commonly follow a "typing on → stream → typing off"
arc, e.g. an AI agent that streams a visible answer and then seals the
stream:

```
typing.update{is_typing:true}
message.created(msg_id=M1)
message.add(msg_id=M1, sequence=0, delta="Hello")   ×
message.add(msg_id=M1, sequence=1, delta=", world") ×
message.done(msg_id=M1)
typing.update{is_typing:false}
```

Invariants the hub enforces:

- Every uplink event's `sender` is overwritten from the authenticated
  identity. The receiver always knows *who* is typing / streaming / replying.
- `typing.update` is delivered to every member of `chat_id` except the
  sender. It never loops back to the sender.
- Streaming events share the producer-chosen `message_id`; the server
  does not rewrite it.
- Online streaming producers SHOULD NOT emit a trailing materialized
  `message.reply` after `message.done`; `message.done` already carries the
  full merged fragments. Sending both can render duplicate visible replies
  in clients that do not collapse live lifecycle frames with materialized
  replies.
- On `message.add`, each text fragment MUST carry both `text` and `delta`.

## Streaming uplink rule

A streaming producer — typically an AI agent connected over WS — MAY
push the lifecycle events as uplink envelopes:

- `payload.message_id` is chosen by the client and MUST stay identical
  across every event in one stream.
- `payload.sequence` MUST be monotonic starting at 0 on the first
  `message.add`.
- Top-level `sender` is always overwritten from the authenticated identity
  on uplink; any client-supplied value is discarded.
- `chat_id` is REQUIRED — streaming events fan out through the same chat
  routing as `message.send`. The server stamps `chat_type` on the downlink.
- The server does NOT emit a `message.ack` for streaming uplinks — acking
  every `message.add` would flood the sender. Producers SHOULD watch for
  `message.failed` on the downlink side to detect trouble.

Downstream path: handler resolves chat members → produces one Kafka record
per recipient (key = recipient user id) onto `im.messages`. msghub forwards
records to all of that recipient's online WebSocket devices. notification
stores durable inbox records for device replay, sends Push reminders for
materialized `message.send/message.reply`, and collects offline streaming
lifecycle events into a single replayable `message.reply` (see *Streaming
replay rule*).

## Streaming replay rule

When a recipient device is not caught up during a streaming session
(`message.created` → `message.add`* → `message.done`), the server does
**not** need to replay every lifecycle event to that device. Instead, once
the stream completes, the durable replay record SHOULD be a single
`message.reply` envelope whose `payload.message` carries the full merged
`fragments` (no `delta`), a materialized
`streaming: {status:"static", mutation_policy:"sealed"}`, and the same
`message_id` as the stream.

This ensures reconnecting or lagging devices receive the complete final
content without having to re-materialize from deltas. Device replay uses the
same materialized envelope for missed completed streams.

## Contract checks

- Client-originated `message.send` / `message.reply` must omit top-level `sender`, payload `message_id`, and `message.streaming`.
- Server-originated `message.send` / `message.reply` must include top-level `sender`, payload `message_id`, and a fully materialized non-streaming `message`.
- `message.send.payload.message` / `message.reply.payload.message` must never include nested `chat`, nested `sender`, nested `to`, or removed timestamp fields.
- `message.created` starts the stream for one `payload.message_id`. Minimal shape — only `message_id` (and optional `message_mode`) is required.
- `message.add` MUST carry `payload.{message_id, sequence, mutation, fragments, streaming, added_at}`; every text fragment MUST carry both `text` (cumulative) and `delta` (new piece).
- `message.done` MUST carry `payload.{message_id, fragments, streaming, completed_at}` with `streaming.status == "done"`; fragments do NOT carry `delta`.
- `message.failed` mirrors `message.done` but with `streaming.status == "failed"`.
- All streaming lifecycle events reuse the same payload-level `message_id` established by `message.created`.
- Routing is driven by top-level `chat_id` alone — the hub resolves the chat members and fans out to everyone except the sender.
- Top-level `to` is UI context only, never routing.
- `chat_type` is server-stamped on every downlink; uplinks MUST omit it.
- Conversation `device_list` metadata supplies push tokens only; it does not restrict WebSocket fanout, which targets all currently online devices for the recipient user.
- Missed completed streams should be replayed as a single `message.reply` with the full merged fragments instead of replaying `message.created`, `message.add`, or `message.done` individually.
- Servers replay missed messages as normal downlink envelopes after the WebSocket session opens and MUST NOT require receiver-side ack frames.
- Device replay advances `user_id + device_id` server-side cursor only after a successful WebSocket write.

Anything that still treats nested message routing, sender-owned client sends, or removed timestamp/correlation fields as canonical is out of contract for this version.
