# WebSocket Logs — `clawchat_gateway/ws_log.py`

Deterministic formatter for ClawChat WebSocket lifecycle log lines.

## API

| Function | Purpose |
|---|---|
| `optional_field(value) -> str` | Normalises optional values for log fields. `None` and empty strings render as `-`; booleans render as lowercase `true` / `false`; other values use `str(value)`. |
| `format_ws_log(...) -> str` | Renders `clawchat.ws` followed by the canonical fixed prefix fields: `event`, `account_id`, `attempt`, `reconnect_count`, `state`, `action`, then any supplied extra fields in caller-provided order. |

All WebSocket protocol/lifecycle logs use this helper so Python output keeps the same field order as the shared ClawChat contract. Sensitive credential material is never passed to the formatter.
