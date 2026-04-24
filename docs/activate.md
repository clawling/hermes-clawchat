# Activate — `src/clawchat_gateway/activate.py`

Exchanges a ClawChat activation (invite) code for a token via `/v1/agents/connect` and persists credentials + streaming defaults into `$HERMES_HOME/config.yaml`.

Exposed as both a Python API (used by the `clawchat_activate` tool handler) and a CLI (`python -m clawchat_gateway.activate CODE`).

## Helpers

| Function | Signature | Purpose |
|---|---|---|
| `_hermes_home` | `() -> Path` | `$HERMES_HOME` or `~/.hermes`. |
| `_load_config` | `() -> tuple[Path, dict]` | Load `~/.hermes/config.yaml`; returns `(path, {})` if missing or malformed. Does not raise. |
| `_write_config` | `(config_path: Path, config: dict) -> None` | Serialise via `yaml.safe_dump(..., allow_unicode=False, sort_keys=False)`; creates parent dirs. |
| `_derive_websocket_url` | `(base_url: str) -> str` | For the two well-known NewBase hosts (`company.newbaselab.com:19001` and `:10086`), return `DEFAULT_WEBSOCKET_URL` verbatim. Otherwise swap `http→ws`/`https→wss` and append `/v1/ws`. |

## `persist_activation`

```python
persist_activation(*, access_token: str, user_id: str, refresh_token: str | None, base_url: str) -> dict
```

Writes into `~/.hermes/config.yaml`:

- `platforms.clawchat.enabled = True`
- `platforms.clawchat.extra`:
  - `base_url` (rstripped)
  - `websocket_url` (`_derive_websocket_url`)
  - `token = access_token`
  - `user_id`
  - `reply_mode = "stream"`
  - `show_tools_output = False`
  - `show_think_output = False`
  - `refresh_token` (only if provided)
- `streaming`:
  - `enabled = True`
  - defaults for `transport = "edit"`, `edit_interval = 0.25`, `buffer_threshold = 16` (via `setdefault`, so not overwritten if already set).
- `display.platforms.clawchat`:
  - `tool_progress = "off"`
  - `show_reasoning = False`

Returns a dict describing the result (tokens are redacted as `"***"`):

```python
{
  "config_path": str,
  "user_id": str,
  "base_url": str,
  "websocket_url": str,
  "token": "***",
  "refresh_token": "***" | None,
  "restart_required": True,
  "restart_message": "Restart Hermes gateway so ClawChat reloads the new credentials.",
}
```

## `activate`

```python
async activate(code: str, *, base_url: str) -> dict
```

1. Build a `ClawChatApiClient(base_url=base_url.rstrip("/"), token="", user_id="")` — the connect call is unauthenticated.
2. `await client.agents_connect(code=code)` — expected payload: `{access_token, refresh_token?, agent: {user_id, ...}}`.
3. Hand off to `persist_activation`.

The caller (`_handle_clawchat_activate` in `__init__.py`) appends `ok: True` and scheduling metadata (`restart_scheduled`, `restart_delay_seconds`, `restart_message`) before returning to the LLM.

## CLI — `main(argv=None) -> int`

```
usage: python -m clawchat_gateway.activate [--base-url URL] CODE
```

- `code` — positional, required.
- `--base-url` — default `DEFAULT_BASE_URL`.

Runs `asyncio.run(activate(...))`, pretty-prints the payload (`ensure_ascii=False, indent=2`), exits 0 on success. API errors bubble up as exceptions (no try/except wrapper in `main`), so the CLI will crash with a traceback on transport / auth failure.
