# WebSocket State — `clawchat_gateway/ws_state.py`

Small reconnect counter helper used by `ClawChatConnection`.

## Types

| Name | Purpose |
|---|---|
| `ReconnectSnapshot` | Immutable `{attempt, reconnect_count}` view for logging. |
| `ReconnectTracker` | Owns the monotonic connection `attempt` counter and consecutive `reconnect_count`. |

`next_connect()` returns `(attempt, reconnect_count)`: the first connection is `(1, 0)`, the first reconnect is `(2, 1)`, and later reconnects continue increasing the second value. `reset_reconnect_count()` is called only after a session has remained ready for the stable-ready window.
