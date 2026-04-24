# Config — `src/clawchat_gateway/config.py`

Frozen dataclass wrapping the `extra` section of hermes-agent's `PlatformConfig` for ClawChat. Accepts snake_case and camelCase keys.

## Helpers

| Function | Signature | Purpose |
|---|---|---|
| `_get_alias` | `(data: dict, snake: str, camel: str, default=None) -> Any` | Look up `snake` first, then `camel`, else `default`. |

## `ClawChatConfig`

```python
@dataclass(frozen=True)
class ClawChatConfig:
    websocket_url: str
    base_url: str = ""
    token: str = ""
    user_id: str = ""
    reply_mode: str = "stream"
    group_mode: str = "mention"
    stream_flush_interval_ms: int = 250
    stream_min_chunk_chars: int = 40
    stream_max_buffer_chars: int = 2000
    reconnect_initial_delay_ms: int = 500
    reconnect_max_delay_ms: int = 15000
    reconnect_jitter_ratio: float = 0.3
    reconnect_max_retries: float = float("inf")
    heartbeat_interval_ms: int = 20000
    heartbeat_timeout_ms: int = 10000
    ack_timeout_ms: int = 15000
    ack_auto_resend_on_timeout: bool = False
    media_local_roots: tuple[str, ...] = field(default_factory=tuple)
    media_download_dir: str = "/tmp/clawchat-media"
    show_tools_output: bool = False
    show_think_output: bool = False
```

Field groups:

- **Connectivity** — `websocket_url`, `base_url`, `token`, `user_id`.
- **Behaviour** — `reply_mode` (`"stream"` enables live delta sends; anything else falls back to a single `message.reply`), `group_mode` (`"mention"` filters inbound group messages to those that @mention `user_id`).
- **Streaming tunables** — `stream_flush_interval_ms`, `stream_min_chunk_chars`, `stream_max_buffer_chars` (currently consumed externally / not by the adapter directly).
- **Reconnect** — initial delay, max delay, jitter ratio, max retries (`float("inf")` ≈ forever).
- **Heartbeat** — `ping_interval` / `ping_timeout` for the WebSocket library (in ms; divided by 1000 in `connection.py`).
- **Ack** — `ack_timeout_ms`, `ack_auto_resend_on_timeout` (wired through but not currently active in the send path).
- **Media** — `media_local_roots` is the allowlist for local file paths in outbound uploads (`media_runtime.ensure_allowed_local_path`); `media_download_dir` is where inbound media is cached.
- **Filtering** — `show_tools_output`, `show_think_output` — when `False`, the adapter strips `<think>` and tool-invocation blocks from visible content.

### Classmethod

`from_platform_config(cls, platform_config) -> ClawChatConfig`

- Reads `platform_config.extra` (default `{}`).
- Nested `extra["stream"]` provides stream tunables.
- `media_local_roots` from `_get_alias(..., "media_local_roots", "mediaLocalRoots", ())` is coerced to a tuple.
- Booleans for `show_tools_output` / `show_think_output` are force-cast with `bool(...)` so truthy strings from env vars round-trip correctly.

**When extending:** add the new field with a default, add an `_get_alias` lookup in `from_platform_config`, and update any writer that persists config (e.g., `activate.persist_activation`, `install.configure_clawchat_streaming`) so the roundtrip stays consistent.
