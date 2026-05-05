# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this repo is

A **Hermes Agent plugin** that integrates the ClawChat messaging platform. It is not a standalone application — at runtime it is loaded into a running hermes-agent process. On Hermes v0.12.0+ it registers the `clawchat` gateway platform directly through `ctx.register_platform(...)`; source patching is only a legacy fallback for older Hermes builds that do not expose the platform registry API.

The root `__init__.py` is the Hermes plugin entrypoint (called by hermes-agent via `register(ctx)`). `plugin.yaml` declares the plugin to Hermes. The `src/clawchat_gateway/` package is the actual gateway adapter, installer, and tool implementations; it is also a pip-installable distribution (`pyproject.toml`, name: `clawchat-gateway`).

## Common commands

All runtime commands must use the **Hermes Python venv**, not the system Python, because the adapter imports `gateway.platforms.base` / `gateway.config` from hermes-agent at runtime. Tests stub these (see "Testing" below), so the system Python is fine for tests only.

```bash
# Run the full test suite (pyproject.toml configures pytest-asyncio auto mode)
pytest

# Single test / single file
pytest tests/test_adapter.py
pytest tests/test_install.py::test_apply_and_remove_patch_with_indentation

# Legacy fallback only: apply patches to an older hermes-agent checkout (idempotent)
python -m clawchat_gateway.install --hermes-dir "$HERMES_DIR"
python -m clawchat_gateway.install --hermes-dir "$HERMES_DIR" --check    # status only
python -m clawchat_gateway.install --hermes-dir "$HERMES_DIR" --dry-run
python -m clawchat_gateway.install --hermes-dir "$HERMES_DIR" --uninstall

# Activate a ClawChat account against the API (writes secrets to ~/.hermes/.env and non-secret config to ~/.hermes/config.yaml)
python -m clawchat_gateway.activate CODE
python -m clawchat_gateway.activate CODE --base-url http://host:port

# Profile updates (requires activation first)
python -m clawchat_gateway.profile nickname "NEW_NAME"
python -m clawchat_gateway.profile avatar /absolute/path/to/image.png
```

The old Node-side install shim `@newbase-clawchat/hermes-clawchat` is not used by the Hermes v0.12+ plugin flow. Prefer `hermes plugins install newbase-clawchat/hermes-clawchat` and `hermes plugins enable clawchat`; the Python installer remains only for legacy patch installs.

## Architecture

### Two-stage boot

1. **Plugin registration** (`__init__.py` → `register(ctx)`): adds `src/` to `sys.path` (also writes a `.pth` file into site-packages so later imports work without re-registration), registers seven Hermes tools (`clawchat_activate`, profile/friends/media helpers), and registers the `skills/clawchat/SKILL.md` skill.
2. **Platform registration** (`_register_platform(ctx)` inside `register`): if Hermes exposes `ctx.register_platform`, registers ClawChat with the adapter factory, validation hooks, allowlist env vars, max message length, emoji, and platform prompt. This is the normal Hermes v0.12.0+ path.
3. **Legacy auto-install fallback** (`_install_gateway()`): only used when `ctx.register_platform` is unavailable. It invokes `clawchat_gateway.install.main(...)` to anchor-patch older hermes-agent source files so they know about the `CLAWCHAT` platform.

After `clawchat_activate` succeeds, the handler schedules a detached `hermes gateway restart` through `clawchat_gateway.restart.schedule_gateway_restart(delay_seconds=2)`. The delay lets the activation response return to the user before the gateway is torn down.

### Legacy anchor-patch installer (`install.py`)

Modern Hermes has a plugin API for adding platforms; use `ctx.register_platform(...)` through the normal plugin entrypoint instead of patching. The installer remains for older Hermes builds and inserts code blocks into hermes-agent's own files by searching for `anchor` strings and wrapping the insertion with `# clawchat-gateway:<id>:start` / `:end` markers. Each `Patch` is idempotent — re-running detects the start marker and skips. Files touched in legacy mode:

- `gateway/config.py` — add `Platform.CLAWCHAT`, env-var overrides, `connected_platforms` check
- `gateway/run.py` — adapter factory case, auth-map entries, post-stream `on_run_complete` hooks, startup allowlist
- `agent/prompt_builder.py` — per-platform prompt hint for ClawChat
- `tools/send_message_tool.py` — map the `"clawchat"` string to `Platform.CLAWCHAT`
- `hermes_cli/platforms.py` — CLI platform registry entry

`configure_clawchat_allow_all()` and `configure_clawchat_streaming()` also write `~/.hermes/.env` (`CLAWCHAT_ALLOW_ALL_USERS=true`) and fill in streaming defaults in `~/.hermes/config.yaml`. Installed state is tracked in `<hermes-dir>/.clawchat_gateway_install_state.json`.

When editing `build_patches()`, if you change an `anchor` string, pick something still present in the current hermes-agent source; if you change a `payload`, also bump or re-scope the `id` so existing installs don't skip your new payload (old marker is still there).

### Gateway runtime (`src/clawchat_gateway/`)

- **`adapter.py`** — `ClawChatAdapter(BasePlatformAdapter)`. Implements `connect/disconnect`, `send`, `edit_message`, `on_run_complete`, `send_typing`, `send_image[_file]`. Holds a map of `_ActiveRun` per in-flight streaming message and uses the `stream` reply mode when available (falls back to a single `message.reply` for media-only or non-stream configs). Filters `<think>` and tool-call blocks out of visible content based on `show_think_output`/`show_tools_output`. Attaches the `clawchat` skill to inbound messages whose text matches `_ACTIVATION_INTENT_RE` so Hermes proactively picks up activation phrases.
- **`connection.py`** — `ClawChatConnection` owns the WebSocket lifecycle: a supervisor task with exponential backoff + jitter reconnect, challenge/`hello-ok` handshake (path `/v1/ws` uses the real-time subprotocol and skips the legacy handshake), an outbound send queue that flushes once `READY`, and a read loop that dispatches `message.send` frames to the adapter. State transitions are reported via `on_state_change`.
- **`protocol.py`** — pure frame builders (`message.created`, `message.add`, `message.done`, `message.reply`, `typing.update`, `connect`) and `compute_client_sign` (HMAC-SHA256 of `client_id|nonce` keyed by token).
- **`inbound.py`** — parses a `message.send` envelope into `InboundMessage`. In `group` chat + `group_mode=mention`, drops frames where the bot's `user_id` is not in `context.mentions`.
- **`stream_buffer.py`** — `compute_delta(last_text, new_text)` for streaming appends.
- **`media_runtime.py`** — outbound uploads via `/media/upload`, inbound downloads into `media_download_dir` (default `/tmp/clawchat-media`). Local outbound paths follow Hermes `MEDIA:` delivery by default; `media_local_roots` / `CLAWCHAT_MEDIA_LOCAL_ROOTS` can be configured to tighten allowed local paths.
- **`api_client.py`** — thin HTTP client using `urllib.request` in a thread (no `requests`/`httpx` dep). Default base URL is `http://company.newbaselab.com:10086`; responses must have envelope `{code: 0, data: {...}}` or `ClawChatApiError` is raised. Handles `/v1/agents/connect`, `/v1/users/me`, `/v1/users/{id}`, `/v1/friends`, `/media/upload`, `/v1/files/upload-url`.
- **`config.py`** — `ClawChatConfig` is a frozen dataclass built from `platform_config.extra`. Supports both snake_case and camelCase keys (`_get_alias`). Do **not** add required fields without also updating `from_platform_config` and the activation writer.
- **`activate.py`** — calls `/v1/agents/connect` with `platform=hermes`, `type=clawbot`, writes `CLAWCHAT_TOKEN` / `CLAWCHAT_REFRESH_TOKEN` to `~/.hermes/.env`, writes non-secret platform settings (`user_id`, `base_url`, `websocket_url`, streaming flags) under `platforms.clawchat.extra` in `~/.hermes/config.yaml`, and configures streaming defaults. The websocket URL is derived from the base URL unless the base is the known NewBase host (which uses `DEFAULT_WEBSOCKET_URL` verbatim).
- **`profile.py`** — nickname/avatar updates. Avatar must be an absolute local path; the command always uploads via `/v1/files/upload-url` first, then PATCHes `/v1/users/me` with the returned URL.
- **`device_id.py`** — stable device ID for the `X-Device-Id` header.

### Skill (`skills/clawchat/SKILL.md`)

Registered directly by `ctx.register_skill("clawchat", ...)` on Hermes v0.12+. Legacy patch installs can also copy it into `$HERMES_HOME/skills/clawchat/` via `install_skill()`. It encodes the activation / profile / media flows as instructions for the Hermes LLM. Keep it and the tool `description` fields in `__init__.py` consistent — both are surfaced to the model and divergent phrasing causes the activation tool to be skipped.

## Testing

`tests/conftest.py` inserts `src/` onto `sys.path` and then `tests/fake_hermes.py` injects stub modules for `gateway`, `gateway.config`, `gateway.platforms`, and `gateway.platforms.base` so the adapter can be imported without a real hermes-agent checkout. When adding imports from `gateway.*` in production code, extend `fake_hermes.py` or the test will fail at import time.

`tests/fake_ws.py` provides an in-memory WebSocket for connection-layer tests. Pytest runs in `asyncio_mode = "auto"` so async tests don't need `@pytest.mark.asyncio`.

## Environment variables

Runtime (read by the Hermes v0.12+ platform registration helpers, the Python modules here, and by installed legacy patches):
- `HERMES_HOME` — Hermes data dir (default `~/.hermes`). Controls where `config.yaml`, `.env`, `skills/`, and `plugins/` live.
- `HERMES_DIR` / `HERMES_AGENT_DIR` — hermes-agent install dir (default `$HERMES_HOME/hermes-agent`, or `/opt/hermes` if present).
- `CLAWCHAT_WEBSOCKET_URL` / `CLAWCHAT_WS_URL`, `CLAWCHAT_BASE_URL`, `CLAWCHAT_TOKEN`, `CLAWCHAT_REFRESH_TOKEN`, `CLAWCHAT_USER_ID`, `CLAWCHAT_REPLY_MODE`, `CLAWCHAT_GROUP_MODE`, `CLAWCHAT_MEDIA_LOCAL_ROOTS` — override values in `platforms.clawchat.extra`; legacy patch installs inject the same values through the `env_overrides` blocks.
- `CLAWCHAT_ALLOWED_USERS`, `CLAWCHAT_ALLOW_ALL_USERS` — auth allowlist, read by hermes-agent.
