 

## Table of contents

1. [Event constants — full list](#1-event-constants--full-list)
2. [Envelope shape](#2-envelope-shape)
3. [Routing & sender shapes](#3-routing--sender-shapes)
4. [Fragment kinds — fields populated per kind](#4-fragment-kinds--fields-populated-per-kind)
5. [Streaming sub-shape](#5-streaming-sub-shape)
6. [Payload type catalogue](#6-payload-type-catalogue)
7. [Field-by-field uplink vs downlink rules](#7-field-by-field-uplink-vs-downlink-rules)
8. [Message ID minting & preservation](#8-message-id-minting--preservation)
9. [Wire examples — the canonical set](#9-wire-examples--the-canonical-set)

---

## 1. Event constants — full list

`pkg/protocol/envelope.go`:

| Constant | Wire value | Direction | Carries `to` | Carries `sender` | Server emits ack? |
|----------|-----------|-----------|--------------|------------------|-------------------|
| `EventConnectChallenge` | `connect.challenge` | S → C | no | no | n/a |
| `EventConnect` | `connect` | C → S | no | no | (`hello-ok` / `hello-fail`) |
| `EventHelloOK` | `hello-ok` | S → C | no | no | n/a |
| `EventHelloFail` | `hello-fail` | S → C | no | no | n/a |
| `EventMessageSend` | `message.send` | C ↔ S | yes (UI) | server-only | yes (`message.ack`) on uplink |
| `EventMessageAck` | `message.ack` | S → C | yes | no | n/a |
| `EventMessageReply` | `message.reply` | C ↔ S | yes (UI) | server-only | yes (`message.ack`) on uplink |
| `EventMessageCreated` | `message.created` | C ↔ S | yes (UI) | server-only | **no** |
| `EventMessageAdd` | `message.add` | C ↔ S | yes (UI) | server-only | **no** |
| `EventMessageDone` | `message.done` | C ↔ S | yes (UI) | server-only | **no** |
| `EventMessageFailed` | `message.failed` | C ↔ S | yes (UI) | server-only | **no** |
| `EventTypingUpdate` | `typing.update` | C ↔ S | yes (UI) | server-injected | **no** |
| `EventOfflineBatch` | `offline.batch` | S → C | no | no | deprecated legacy replay |
| `EventOfflineAck` | `offline.ack` | C → S | no | no | deprecated legacy replay |
| `EventOfflineDone` | `offline.done` | S → C | no | no | deprecated legacy replay |
| `EventPing` | `ping` | C ↔ S | no | no | yes (`pong`) |
| `EventPong` | `pong` | C ↔ S | no | no | n/a |

### Routing constants

| Constant | Wire value |
|----------|-----------|
| `RoutingDirect` | `direct` |
| `RoutingGroup` | `group` |

> **Legacy alias:** `chat` is accepted at the resolver layer (HTTP / Redis
> records, mock seed strings) and normalised to `direct` before it ever
> appears on the wire. Clients must use `direct` / `group` only.

---

## 2. Envelope shape

`pkg/protocol/envelope.go:Envelope`:

```go
type Envelope struct {
    Version   string          `json:"version"`              // always "2"
    Event     string          `json:"event"`
    TraceID   string          `json:"trace_id"`
    EmittedAt int64           `json:"emitted_at"`           // milliseconds since epoch
    ChatID    string          `json:"chat_id,omitempty"`    // routing field (business events)
    ChatType  string          `json:"chat_type,omitempty"`  // server-stamped on downlink only
    To        *Routing        `json:"to,omitempty"`         // UI context only; never used for routing
    Sender    *Sender         `json:"sender,omitempty"`     // server-stamped on downlink
    Payload   json.RawMessage `json:"payload"`              // event-specific body
}
```

### Field rules

| Field | Required by | Notes |
|-------|-------------|-------|
| `version` | every frame | currently `"2"` |
| `event` | every frame | one of the constants above |
| `trace_id` | every frame | client-chosen on uplink; server echoes on the matching response |
| `emitted_at` | every frame | server restamps on `typing.update` and every streaming lifecycle event |
| `chat_id` | every business event (`message.*`, `typing.update`) | empty/missing on `connect.*`, `hello-*`, `offline.*`, `ping`, `pong` |
| `chat_type` | downlink business events | server-stamped from resolver; uplink values are dropped |
| `to` | optional everywhere | preserved verbatim end-to-end as UI context |
| `sender` | downlink business events | uplink values are dropped and overwritten |
| `payload` | every frame | shape varies per event — see §6 |

---

## 3. Routing & sender shapes

```go
type Routing struct {
    ID   string `json:"id"`           // chat_id or user_id depending on type
    Type string `json:"type"`         // "direct" | "group"
}

type Sender struct {
    ID       string `json:"id"`        // user_id
    Type     string `json:"type"`      // always "direct" (Sender always identifies a single user)
    NickName string `json:"nick_name"`
}
```

> Even on a group chat downlink, `sender.type == "direct"` — `sender`
> always identifies the one user who originated the frame.

---

## 4. Fragment kinds — fields populated per kind

`pkg/protocol/events.go:Fragment`:

```go
type Fragment struct {
    Kind     string `json:"kind"`               // discriminator
    Text     string `json:"text,omitempty"`
    Delta    string `json:"delta,omitempty"`    // text-only, message.add only
    UserID   string `json:"user_id,omitempty"`
    Display  string `json:"display,omitempty"`
    URL      string `json:"url,omitempty"`
    Name     string `json:"name,omitempty"`
    Mime     string `json:"mime,omitempty"`
    Size     int64  `json:"size,omitempty"`     // bytes
    Width    int    `json:"width,omitempty"`    // pixels
    Height   int    `json:"height,omitempty"`   // pixels
    Duration int64  `json:"duration,omitempty"` // milliseconds
}
```

### Per-kind populated fields

| `kind` | Populated fields |
|--------|------------------|
| `text` | `text`; `delta` ONLY on `message.add` |
| `mention` | `user_id`, `display` (display optional) |
| `image` | `url`, `name?`, `mime?`, `size?`, `width?`, `height?` |
| `video` | `url`, `name?`, `mime?`, `size?`, `width?`, `height?`, `duration?` |
| `audio` | `url`, `name?`, `mime?`, `size?`, `duration?` |
| `file` | `url`, `name?`, `mime?`, `size?` |

**Unknown `kind` values** must be preserved by intermediaries and
rendered as "unsupported content" by clients.

### `delta` invariant

On `message.add`, every text fragment carries both `text` (cumulative
content so far) and `delta` (the new piece this round). Across consecutive
adds for the same fragment index:

```
text_n_minus_1 + delta_n  ==  text_n
```

`delta` is **absent** on `message.created`, `message.done`, and the
materialized `message.send` / `message.reply`.

---

## 5. Streaming sub-shape

`pkg/protocol/events.go:Streaming`:

```go
type Streaming struct {
    Status         string `json:"status"`            // "static" | "streaming" | "done"
    Sequence       int    `json:"sequence"`
    MutationPolicy string `json:"mutation_policy"`   // "sealed" | "append_text_only"
    StartedAt      *int64 `json:"started_at"`        // nullable, ms since epoch
    CompletedAt    *int64 `json:"completed_at"`      // nullable, ms since epoch
}
```

| `status` | When it appears | Typical `mutation_policy` |
|----------|-----------------|---------------------------|
| `static` | Materialized `message.send` / `message.reply` | `sealed` |
| `streaming` | `message.created` / `message.add` (in flight) | `append_text_only` |
| `done` | `message.done` (final fragments) | `append_text_only` |

`message.failed` does not produce a `Streaming` block on the offline
side (the buffer is dropped; nothing materializes).

---

## 6. Payload type catalogue

All from `pkg/protocol/events.go` unless noted.

### Auth & handshake

```go
type ChallengePayload struct { Nonce string `json:"nonce"` }
type ConnectPayload struct {
    Token        string              `json:"token"`
    Nonce        string              `json:"nonce"`
    DeviceID     string              `json:"device_id,omitempty"`
    Capabilities ConnectCapabilities `json:"capabilities,omitempty"`
}
type ConnectCapabilities struct {
    MultiDevice  bool `json:"multi_device,omitempty"`
    DeviceReplay bool `json:"device_replay,omitempty"`
}
type HelloOKPayload struct {
    DeviceID     string `json:"device_id,omitempty"`
    DeliveryMode string `json:"delivery_mode,omitempty"`
}
type HelloFailPayload struct { Reason string `json:"reason"` }
```

When `connect.payload.device_id` is omitted, the server uses the authenticated
`user_id`. `hello-ok.payload.delivery_mode` is currently `"device_replay"` for
all accepted clients. If the same `user_id + device_id` is already connected on
the msghub instance, the later socket is closed without `hello-ok` or
`hello-fail`.

> **`connect.payload.capabilities` is accepted but currently ignored** by the
> server. Device replay runs unconditionally on every connection
> (`cmd/msghub/main.go` sets `client.DeviceReplay = true` for every accepted
> client and stamps `delivery_mode: "device_replay"` on `hello-ok`). The
> `multi_device` and `device_replay` flags exist on the wire so future
> server versions can negotiate them, and so client SDKs can advertise
> support today without a wire-format break later. Do not depend on the
> server reflecting a `false` capability back as "feature off".

`hello-fail.reason` values:

- `"nonce mismatch"`
- `"authentication failed"`
- `"invalid connect event"`
- `"invalid connect payload"`

### Materialized message frames

```go
type MessageSendPayload struct {
    MessageID   string  `json:"message_id,omitempty"`   // omitempty on uplink, present on downlink
    MessageMode string  `json:"message_mode"`            // "normal" by default
    Message     Message `json:"message"`
}

type Message struct {
    Body      Body            `json:"body"`
    Context   MessageContext  `json:"context"`
    Streaming *Streaming      `json:"streaming,omitempty"` // present on downlink only
}

type Body struct {
    Fragments []Fragment `json:"fragments"`
}

type MessageContext struct {
    Mentions []any          `json:"mentions"`           // free-form; no Mention struct in code
    Reply    *ReplyContext  `json:"reply"`              // null when not a reply
}

type ReplyContext struct {
    ReplyToMsgID string        `json:"reply_to_msg_id"`
    ReplyPreview *ReplyPreview `json:"reply_preview"`   // serialises as null on non-reply messages
}

type ReplyPreview struct {
    ID        string     `json:"id"`                    // sender user_id of the original
    NickName  string     `json:"nick_name"`
    Fragments []Fragment `json:"fragments"`             // a preview, not necessarily complete
}

type MessageAckPayload struct {
    MessageID  string `json:"message_id"`
    AcceptedAt int64  `json:"accepted_at"`              // server clock, ms
}
```

### Streaming lifecycle frames (flat payload — NOT wrapped in `message`)

```go
type StreamCreatedPayload struct {
    MessageID   string `json:"message_id"`
    MessageMode string `json:"message_mode,omitempty"`
}

type StreamAddPayload struct {
    MessageID string     `json:"message_id"`
    Sequence  int        `json:"sequence"`              // monotonic from 0
    Mutation  *Mutation  `json:"mutation,omitempty"`
    Fragments []Fragment `json:"fragments"`             // cumulative, with delta
    Streaming *Streaming `json:"streaming,omitempty"`
    AddedAt   int64      `json:"added_at,omitempty"`
}

type Mutation struct {
    Type                string `json:"type"`            // "append" | …
    TargetFragmentIndex *int   `json:"target_fragment_index"` // nullable
}

type StreamDonePayload struct {
    MessageID   string     `json:"message_id"`
    Fragments   []Fragment `json:"fragments"`           // cumulative final, NO delta
    Streaming   *Streaming `json:"streaming,omitempty"` // status: "done"
    CompletedAt int64      `json:"completed_at,omitempty"`
}
// `message.failed` reuses the StreamDonePayload shape with `streaming.status: "failed"`.
// There is no separate `StreamFailedPayload` Go type — do not grep for one.
```

### Offline replay

```go
type OfflineBatchPayload struct {
    BatchID   int        `json:"batch_id"`
    Items     []Envelope `json:"items"`                 // fully materialized downlink envelopes
    Remaining int        `json:"remaining"`             // items left after this batch
}

type OfflineAckPayload struct {
    BatchID int `json:"batch_id"`
}

type OfflineDonePayload struct {}
```

### Typing & ping/pong

```go
type TypingUpdatePayload struct {
    IsTyping bool `json:"is_typing"`
}

// Ping / pong payloads are empty objects: `{ "payload": {} }`.
```

---

## 7. Field-by-field uplink vs downlink rules

The matrix below combines `pkg/protocol/`, `internal/msghub/handler.go`,
and `internal/msghub/envelope.go`.

| Field | Uplink (client → server) | Downlink (server → client) |
|-------|--------------------------|----------------------------|
| `version` | `"2"` | `"2"` |
| `event` | client chooses; server validates against the constants list | server-chosen |
| `trace_id` | client chooses | echoed on the matching ack/response |
| `emitted_at` | client clock; server **overwrites** on streaming + typing | server clock |
| `chat_id` | **required** on every business event; empty/missing rejected | echoed |
| `chat_type` | **must be omitted**; client values are dropped | server stamps from `chat.Resolver` |
| `to` | optional; preserved verbatim | echoed verbatim (UI context) |
| `sender` | **must be omitted**; client values are dropped | server stamps from authenticated identity |
| `payload.message_id` | optional on `message.send`/`message.reply`; if present, **preserved verbatim**. Required on every streaming lifecycle event (and identical across the stream). | always populated on downlinks of `message.send`/`message.reply`/`message.ack` and on every streaming downlink |
| `payload.message.streaming` | **must be omitted** on uplink `message.send`/`message.reply` | server fills with `{status:"static", mutation_policy:"sealed", started_at:null, completed_at:null}` |
| `payload.message.body` | required | echoed |
| `payload.message.context` | required (mentions / reply may be empty / null) | echoed |

### Server-injected fields summary

The server overwrites or fills, regardless of what the client sends:

- `sender` (always, every uplink including streaming)
- `chat_type` (every downlink)
- `payload.message_id` when omitted on `message.send` / `message.reply`
- `emitted_at` on `typing.update` and every streaming lifecycle event
- `payload.message.streaming` on materialized `message.send` / `message.reply` downlinks

---

## 8. Message ID minting & preservation

`internal/msghub/envelope.go:ToDownlink`:

```go
if payload.MessageID == "" {
    payload.MessageID = generateMessageID()  // "msg-" + ULID
}
```

`generateMessageID` uses `oklog/ulid/v2` with `ulid.Timestamp(time.Now())`
and `crypto/rand`.

### Why preservation matters

The streaming finalize-reply pattern depends on a deliberate collision
between two writes to the offline store:

```
producer → message.created(M1)
        → message.add(M1, …)
        → message.done(M1)             # StreamCollector materializes a "merged reply"
                                        # row (user_id, message_id=M1) is upserted
        → message.reply(message_id=M1) # uplink reuses the same id
                                        # ConsumerHandler stores again under (user_id, M1);
                                        # ON CONFLICT DO UPDATE replaces the merged row
                                        # → user sees only the polished reply on replay
```

If the server *re-minted* `message.reply.message_id` here, the offline
store would carry both rows and the user would see two messages.

### Media object ID

`internal/media/service.go`: object key = `"media/" + ULID + ext`. Same
ULID library, different prefix. The URL is the capability (unguessable
path); no separate token needed.

---

## 9. Wire examples — the canonical set

These are the exact frames asserted by `internal/msghub/*_test.go` and
`e2e/*_test.go`. Use them as ground truth.

### `connect.challenge` (S → C)

```json
{
  "version": "2",
  "event":   "connect.challenge",
  "trace_id": "trace-challenge-01",
  "emitted_at": 1776162600000,
  "payload": { "nonce": "Wn9hZ3lJZkN1QXBkUEpYbg" }
}
```

### `connect` (C → S)

```json
{
  "version": "2",
  "event":   "connect",
  "trace_id": "t1",
  "emitted_at": 1776162600100,
  "payload": {
    "token": "token-alice",
    "nonce": "Wn9hZ3lJZkN1QXBkUEpYbg"
  }
}
```

### `hello-ok` / `hello-fail`

```json
{ "version": "2", "event": "hello-ok",   "trace_id": "t1", "emitted_at": 1776162600200, "payload": {} }
```

```json
{ "version": "2", "event": "hello-fail", "trace_id": "t1", "emitted_at": 1776162600200,
  "payload": { "reason": "nonce mismatch" } }
```

### `message.send` uplink (Alice → chat-ab)

```json
{
  "version": "2",
  "event":   "message.send",
  "trace_id": "trace-send-01",
  "emitted_at": 1776162600000,
  "chat_id":  "chat-ab",
  "to":       { "id": "chat-ab", "type": "direct" },
  "payload": {
    "message_mode": "normal",
    "message": {
      "body":    { "fragments": [{ "kind": "text", "text": "hi bob" }] },
      "context": { "mentions": [], "reply": null }
    }
  }
}
```

### `message.ack` (back to Alice)

```json
{
  "version": "2",
  "event":   "message.ack",
  "trace_id": "trace-send-01",
  "emitted_at": 1776162601000,
  "chat_id":  "chat-ab",
  "to":       { "id": "chat-ab", "type": "direct" },
  "payload": {
    "message_id":  "msg-01HVB6S7K8L9M0N1P2Q3R4S5T6",
    "accepted_at": 1776162601000
  }
}
```

### `message.send` downlink (to Bob)

```json
{
  "version": "2",
  "event":   "message.send",
  "trace_id": "trace-send-downlink-01",
  "emitted_at": 1776162601500,
  "chat_id":   "chat-ab",
  "chat_type": "direct",
  "to":     { "id": "chat-ab",   "type": "direct" },
  "sender": { "id": "user-alice", "type": "direct", "nick_name": "Alice" },
  "payload": {
    "message_id":   "msg-01HVB6S7K8L9M0N1P2Q3R4S5T6",
    "message_mode": "normal",
    "message": {
      "body":      { "fragments": [{ "kind": "text", "text": "hi bob" }] },
      "context":   { "mentions": [], "reply": null },
      "streaming": {
        "status": "static", "sequence": 0, "mutation_policy": "sealed",
        "started_at": null, "completed_at": null
      }
    }
  }
}
```

### Streaming sequence

```jsonc
// 1) Open the stream
{ "version": "2", "event": "message.created", "chat_id": "chat-alice", "chat_type": "direct",
  "payload": { "message_id": "agent-stream-01K..." } }

// 2) Append fragments — text MUST carry both `text` (cumulative) and `delta` (new piece)
{ "version": "2", "event": "message.add", "chat_id": "chat-alice", "chat_type": "direct",
  "payload": {
    "message_id": "agent-stream-01K...",
    "sequence":   3,
    "mutation":   { "type": "append", "target_fragment_index": null },
    "fragments":  [{ "kind": "text", "text": "Hello, world", "delta": ", world" }],
    "streaming":  { "status": "streaming", "sequence": 3,
                    "mutation_policy": "append_text_only",
                    "started_at": null, "completed_at": null },
    "added_at":   1776406831114
  } }

// 3) Finalize — fragments cumulative, NO `delta`
{ "version": "2", "event": "message.done", "chat_id": "chat-alice", "chat_type": "direct",
  "payload": {
    "message_id": "agent-stream-01K...",
    "fragments":  [{ "kind": "text", "text": "Hello, world" }],
    "streaming":  { "status": "done", "sequence": 3,
                    "mutation_policy": "append_text_only",
                    "started_at": null, "completed_at": 1776406831120 },
    "completed_at": 1776406831120
  } }

// 4) (Optional) trailing reply that REUSES the stream's id — collapses offline store
{ "version": "2", "event": "message.reply", "chat_id": "chat-alice", "chat_type": "direct",
  "payload": {
    "message_id":   "agent-stream-01K...",
    "message_mode": "normal",
    "message": {
      "body":    { "fragments": [{ "kind": "text", "text": "Hello, world" }] },
      "context": {
        "mentions": [],
        "reply": {
          "reply_to_msg_id": "user-msg-01K...",
          "reply_preview":   {
            "id":        "user-alice",
            "nick_name": "Alice",
            "fragments": [{ "kind": "text", "text": "hi" }]
          }
        }
      }
    }
  } }
```

### Device replay sequence

```jsonc
// After hello-ok, missed messages are sent as ordinary downlink envelopes.
{ "version": "2", "event": "message.send", "trace_id": "trace-replay-01",
  "emitted_at": 1776162700000, "chat_id": "chat-ab", "chat_type": "direct",
  "to": { "id": "chat-ab", "type": "direct" },
  "sender": { "id": "user-alice", "type": "direct", "nick_name": "Alice" },
  "payload": { "message_id": "msg-...", "message_mode": "normal", "message": {} } }
```

The replay cursor is server-side and keyed by `user_id + device_id`. New devices
start at the current inbox tail; existing devices resume after their last
successful WebSocket write.

### Ping / pong

```json
{ "version": "2", "event": "ping", "trace_id": "p1", "emitted_at": 1776162600000, "payload": {} }
```

```json
{ "version": "2", "event": "pong", "trace_id": "p1", "emitted_at": 1776162600005, "payload": {} }
```
