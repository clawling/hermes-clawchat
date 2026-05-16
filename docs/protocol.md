# Protocol — `clawchat_gateway/protocol.py`

Pure frame builders and encoding helpers for ClawChat Protocol v2. No I/O, no async, no shared state — every function is a pure transform from arguments to a new frame `dict` (or string / bytes).

For the wire-protocol semantics (event names, payload field meanings, error codes), see [`clawchat-protocol-reference.md`](./clawchat-protocol-reference.md). This file documents the Python module surface.

## Encoding

| Function | Signature | Behaviour |
|---|---|---|
| `encode_frame` | `(frame: dict) -> str` | `json.dumps(frame, separators=(",", ":"), ensure_ascii=False)` — compact, Unicode preserved. |
| `decode_frame` | `(text: str) -> dict` | `json.loads`; raises `ValueError("frame must be object")` if the parsed value is not a dict. |
| `new_frame_id` | `(prefix: str = "req") -> str` | `f"{prefix}-{uuid4()}"`. Used for `trace_id` on outbound frames. |

## Connect handshake

`build_connect_request(frame_id, token, nonce, device_id=None, capabilities=None)`
builds the msghub-compatible `connect` frame used after
`connect.challenge`. Its payload contains token, nonce, optional device id,
and optional capabilities. Hermes passes `{multi_device: true,
device_replay: true}` so missed-message replay arrives as ordinary downlink
envelopes after `hello-ok`; legacy `offline.batch`, `offline.ack`, and
`offline.done` are compatibility events only.

## Message envelope

`_message_envelope(event, *, chat_id, chat_type, payload)` is the shared inner helper. All `message.*` and `typing.*` builders go through it and produce frames of shape:

```json
{
  "version": "2",
  "event": "<event>",
  "trace_id": "trace-<uuid>",
  "chat_id": "<chat_id>",
  "payload": { ... }
}
```

`chat_type` is accepted by every builder for symmetry, but is currently not stamped into the envelope (the gateway derives it from the chat).

## Streaming reply builders

| Function | Outbound `event` | Payload shape |
|---|---|---|
| `build_message_created_event` | `message.created` | `{message_id}` |
| `build_message_add_event` | `message.add` | `{message_id, sequence, mutation: {type:"append", target_fragment_index: null}, fragments:[{kind:"text", text:full_text, delta}], streaming:{status:"streaming", sequence, mutation_policy:"append_text_only", started_at:null, completed_at:null}, added_at:<now_ms>}` |
| `build_message_done_event` | `message.done` | `{message_id, fragments, streaming:{status:"done", sequence, mutation_policy:"append_text_only", started_at:null, completed_at:<now_ms>}, completed_at:<now_ms>}` |
| `build_message_failed_event` | `message.failed` | `{message_id, sequence, reason, streaming:{status:"failed", sequence, mutation_policy:"append_text_only", started_at:null, completed_at:<now_ms>}, completed_at:<now_ms>, fragments?: [{kind:"text", text:reason}]}`. `fragments` is omitted when `reason` is empty/whitespace. |

## Static reply / typing

| Function | Outbound `event` | Payload shape |
|---|---|---|
| `build_message_reply_event` | `message.reply` | `{message_mode:"normal", message:{body:{fragments}, context:{mentions:[], reply: {reply_to_msg_id, reply_preview:null} \| null}}, message_id?}`. `message_id` is included only when `include_message_id=True`. |
| `build_typing_update_event` | `typing.update` | `{is_typing: bool}` |

## Notes when extending

- Every builder is **pure**: timestamps come from `time.time()` at call time, but no shared state or locks. Tests can call them directly and assert on the dict shape.
- New events should preserve the `_message_envelope` skeleton (`version: "2"`, `trace_id` from `new_frame_id`) so the connection-layer logging and dispatcher remain uniform.
- When you add a new `streaming.status` value, also update the corresponding state-machine handling in `adapter.py::_ActiveRun` and the receiver expectations in `clawchat-protocol-reference.md`.
