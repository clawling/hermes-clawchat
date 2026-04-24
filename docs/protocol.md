# Protocol — `src/clawchat_gateway/protocol.py`

Pure functions for ClawChat WebSocket frames. No I/O, no module state. All builders produce `dict`; `encode_frame` serializes to JSON.

## Frame envelope

Common envelope produced by `_message_envelope`:

```python
{
  "version": "2",
  "event": <event-name>,
  "trace_id": new_frame_id("trace"),
  "chat_id": <chat_id>,
  "chat_type": <chat_type>,
  "payload": <payload dict>,
}
```

`connect` frames use the same top-level keys minus `chat_id` / `chat_type`.

## Frame IDs & codecs

| Function | Signature | Purpose |
|---|---|---|
| `new_frame_id` | `(prefix: str = "req") -> str` | `f"{prefix}-{uuid.uuid4()}"`. |
| `encode_frame` | `(frame: dict) -> str` | `json.dumps(frame, separators=(",", ":"), ensure_ascii=False)`. |
| `decode_frame` | `(text: str) -> dict` | `json.loads` + type check. Raises `ValueError` when the decoded value is not a dict. |

## Handshake

| Function | Signature | Purpose |
|---|---|---|
| `compute_client_sign` | `(client_id: str, nonce: str, token: str) -> str` | `hmac.new(token, f"{client_id}|{nonce}", sha256).hexdigest()`. |
| `extract_nonce` | `(frame: dict) -> str \| None` | Reads `payload.nonce` or `payload.data.nonce`. |
| `is_hello_ok` | `(frame: dict, expected_request_id: str) -> bool` | `True` if `event == "hello-ok"`, or `type == "res"` with matching `requestId` and `payload.type == "hello-ok"`. |
| `build_connect_request` | `(*, frame_id: str, token: str, client_id: str, client_version: str, sign: str) -> dict` | `event: "connect"`; `payload: {token, client_id, client_version, sign}`. `trace_id` is `frame_id`. |

## Message events

| Function | Signature | Event | Payload shape |
|---|---|---|---|
| `build_message_created_event` | `(*, chat_id, chat_type, message_id) -> dict` | `message.created` | `{"message_id": ...}` |
| `build_message_add_event` | `(*, chat_id, chat_type, message_id, full_text, delta, sequence) -> dict` | `message.add` | `{message_id, sequence, mutation: {type: "append", target_fragment_index: None}, fragments: [{kind: "text", text, delta}], streaming: {status: "streaming", sequence, mutation_policy: "append_text_only", started_at, completed_at}, added_at: now_ms}` |
| `build_message_done_event` | `(*, chat_id, chat_type, message_id, fragments, sequence) -> dict` | `message.done` | `{message_id, fragments, streaming: {status: "done", sequence, mutation_policy: "append_text_only", started_at, completed_at: now_ms}, completed_at: now_ms}` |
| `build_message_reply_event` | `(*, chat_id, chat_type, message_id, fragments, reply_to_message_id=None) -> dict` | `message.reply` | `{message_id, message_mode: "normal", message: {body: {fragments}, context: {mentions: [], reply: {reply_to_msg_id, reply_preview: None} \| None}}}` |
| `build_typing_update_event` | `(*, chat_id, chat_type, active: bool) -> dict` | `typing.update` | `{is_typing: active}` (not routed through `_message_envelope`; carries its own top-level fields). |

## Private helpers

| Function | Signature | Purpose |
|---|---|---|
| `_message_envelope` | `(event: str, *, chat_id: str, chat_type: str, payload: dict) -> dict` | Assemble the standard envelope used by `build_message_*`. |

## Notes

- `build_message_add_event` and `build_message_done_event` stamp `time.time() * 1000` as `added_at` / `completed_at` — the caller is not expected to supply timestamps.
- `fragments` for `build_message_done_event` and `build_message_reply_event` is already-built and not validated here; the adapter calls `_build_fragments` before invoking these.
- `build_message_reply_event` always emits `context.mentions = []`; group-mention behaviour lives in inbound parsing (`inbound.parse_inbound_message`), not outbound.
