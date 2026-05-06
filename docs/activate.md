# Activate — `clawchat_gateway/activate.py`

Exchanges a ClawChat activation (invite) code for a token via `/v1/agents/connect`, persists secrets into `$HERMES_HOME/.env`, and writes non-secret platform settings + streaming defaults into `$HERMES_HOME/config.yaml`.

Exposed as both a Python API (used by the `clawchat_activate` tool handler) and a CLI (`python -m clawchat_gateway.activate CODE`).

## Helpers

| Function | Signature | Purpose |
|---|---|---|
| `_hermes_home` | `() -> Path` | `$HERMES_HOME` or `~/.hermes`. |
| `_load_config` | `() -> tuple[Path, dict]` | Load `~/.hermes/config.yaml`; returns `(path, {})` if missing or malformed. Does not raise. |
| `_write_config` | `(config_path: Path, config: dict) -> None` | Serialise via `yaml.safe_dump(..., allow_unicode=False, sort_keys=False)`; creates parent dirs. |
| `_env_path` | `() -> Path` | `$HERMES_HOME/.env`. |
| `_validate_env_value` | `(key: str, value: str) -> str` | Reject `\n` / `\r` in `.env` values to keep the line-based format intact. Raises `ValueError` when invalid; returns `value` otherwise. |
| `_write_env_values` | `(values: dict[str, str \| None]) -> Path` | Upsert selected `KEY=value` lines in `.env`; preserve unrelated lines; remove keys whose value is `None`. Each non-`None` value goes through `_validate_env_value`. |
| `_derive_websocket_url` | `(base_url: str) -> str` | For the two well-known NewBase hosts (`company.newbaselab.com:19001` and `:10086`), return `DEFAULT_WEBSOCKET_URL` verbatim. Otherwise swap `http→ws`/`https→wss` and append `/v1/ws`. |

## `persist_activation`

```python
persist_activation(*, access_token: str, user_id: str, refresh_token: str | None, base_url: str) -> dict
```

Writes into `~/.hermes/.env`:

- `CLAWCHAT_TOKEN = access_token`
- `CLAWCHAT_REFRESH_TOKEN = refresh_token` when present, or removes any stale `CLAWCHAT_REFRESH_TOKEN` when absent.

Writes into `~/.hermes/config.yaml`:

- `platforms.clawchat.enabled = True`
- `platforms.clawchat.extra`:
  - `base_url` (rstripped)
  - `websocket_url` (`_derive_websocket_url`)
  - `user_id`
  - `reply_mode = "stream"`
  - `show_tools_output = False`
  - `show_think_output = False`
  - stale `token` / `refresh_token` keys are removed if they were written by an older version.
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
  "env_path": str,
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
usage: python -m clawchat_gateway.activate [--base-url URL] [--no-restart] CODE
```

- `code` — positional, required. `.strip()`-ed before being passed to `activate(...)`.
- `--base-url` — default `DEFAULT_BASE_URL`.
- `--no-restart` — skip the detached `hermes gateway restart` that would otherwise be dispatched after activation succeeds. Useful when chaining the CLI with another orchestrator that controls restart timing.

Runs `asyncio.run(activate(...))`. On success (and unless `--no-restart` is passed):

1. Imports `clawchat_gateway.restart.schedule_gateway_restart` and calls it with `delay_seconds=2`.
2. Augments the printed payload with `restart_scheduled: True`, `restart_delay_seconds: 2`, `restart_command: <resolved sh -lc string>`, and `restart_message: "ClawChat activation saved. Hermes gateway restart dispatched in the background."`.
3. Pretty-prints the payload (`ensure_ascii=False, indent=2`) and exits 0.

API errors bubble up as exceptions (no try/except wrapper in `main`), so the CLI crashes with a traceback on transport / auth failure. The Hermes tool handler `_handle_clawchat_activate` catches these and converts them to a `_tool_error` envelope; it also schedules the restart on its own path independent of the CLI flag.
