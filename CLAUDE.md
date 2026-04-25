# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **Hermes Agent plugin** that integrates the ClawChat messaging platform. It is not a standalone application — at runtime it is loaded into a running hermes-agent process and (on first install) patches hermes-agent's own source files to register a new `CLAWCHAT` platform.

**Distribution model: out-of-tree plugin only.** This project ships exclusively as an installable plugin and is **not** intended to be merged into hermes-agent's source tree. All integration with hermes-agent happens through the runtime anchor-patch installer in `src/clawchat_gateway/install.py`. When evaluating whether a gap is in scope, runtime patches that affect message flow / routing / auth are owned by this plugin; CLI/UX/diagnostic surfaces inside hermes-agent (e.g. `hermes_cli/status.py`, `hermes_cli/dump.py`, `hermes_cli/tools_config.py`, gateway setup wizards, upstream docs) are **not** the plugin's responsibility.

The root `__init__.py` is the Hermes plugin entrypoint (called by hermes-agent via `register(ctx)`). `plugin.yaml` declares the plugin to Hermes. The `src/clawchat_gateway/` package is the actual gateway adapter, installer, and tool implementations; it is also a pip-installable distribution (`pyproject.toml`, name: `clawchat-gateway`).

## Directory structure

- `__init__.py` — Hermes plugin entrypoint (`register(ctx)`); registers tools + skill, then triggers anchor-patch install.
- `plugin.yaml` — plugin manifest declared to Hermes.
- `pyproject.toml` — pip-installable distribution (`clawchat-gateway`).
- `src/clawchat_gateway/` — gateway runtime package:
  - `adapter.py` — `ClawChatAdapter(BasePlatformAdapter)`; connect/disconnect, send, edit_message (streaming), on_run_complete, typing, image send.
  - `connection.py` — `ClawChatConnection` WebSocket lifecycle (supervisor, handshake, send queue, read loop).
  - `protocol.py` — frame builders and `compute_client_sign` (HMAC-SHA256).
  - `inbound.py` — parses `message.send` envelopes into `InboundMessage`.
  - `stream_buffer.py` — `compute_delta(last_text, new_text)`.
  - `media_runtime.py` — outbound `/media/upload`, inbound download, `media_local_roots` allowlist.
  - `api_client.py` — `urllib`-based HTTP client; envelope `{code:0, data:{...}}` or `ClawChatApiError`.
  - `config.py` — `ClawChatConfig` frozen dataclass from `platform_config.extra`.
  - `activate.py` — `/v1/agents/connect`; writes `~/.hermes/config.yaml`.
  - `profile.py` — nickname/avatar updates.
  - `device_id.py` — stable `X-Device-Id`.
  - `install.py` — anchor-patch installer (`Patch` dataclass, `build_patches`, `apply_patch`, `remove_patch`).
- `skills/clawchat/SKILL.md` — copied to `$HERMES_HOME/skills/clawchat/` by installer.
- `tests/` — pytest suite; `conftest.py` + `fake_hermes.py` stub `gateway.*`; `fake_ws.py` for connection tests.
- `docs/` — internal documentation, including `analyze_report.md` and `custom-gateway-guide.md`.

## Notes

- All runtime commands must use the **Hermes Python venv** (the adapter imports `gateway.platforms.base` / `gateway.config` from hermes-agent at runtime). Tests stub these via `fake_hermes.py`, so the system Python is fine for tests only.
- When adding imports from `gateway.*` in production code, extend `tests/fake_hermes.py` or test imports will fail.
- When editing `build_patches()`: if you change an `anchor`, pick something still present in the current hermes-agent source. If you change a `payload`, also bump or re-scope the patch `id` so existing installs don't skip the new payload (the old marker block is still in place).
- `apply_patch` returns on the **first** anchor match. Anchors must be unique within their target file, or the patch will land in the wrong place silently.
- Plugin registration triggers `_install_gateway()` which runs the anchor-patch installer. Failures are logged but do not abort plugin load. After install, `_refresh_gateway_module_cache()` reloads `gateway.config`, `gateway.run`, and `clawchat_gateway.adapter` so the newly-added `Platform.CLAWCHAT` is visible in the running process.
- After `clawchat_activate` succeeds, `_schedule_gateway_restart()` spawns a detached `sh -lc 'sleep 2; hermes gateway restart'`. The delay lets the activation response return before the gateway is torn down.
- Keep `skills/clawchat/SKILL.md` and the tool `description` fields in `__init__.py` consistent — both are surfaced to the model; divergent phrasing causes the activation tool to be skipped.
- `ClawChatConfig` supports both snake_case and camelCase keys via `_get_alias`. Do **not** add required fields without also updating `from_platform_config` and the activation writer.
- The Node-side install entrypoint `@newbase-clawchat/hermes-clawchat` is not in this repo — it lives in the npm package and ultimately shells out to `python -m clawchat_gateway.install`.
- Pytest runs in `asyncio_mode = "auto"` so async tests don't need `@pytest.mark.asyncio`.

### Environment variables

- `HERMES_HOME` — Hermes data dir (default `~/.hermes`).
- `HERMES_DIR` / `HERMES_AGENT_DIR` — hermes-agent install dir (default `$HERMES_HOME/hermes-agent`, or `/opt/hermes` if present).
- `CLAWCHAT_WEBSOCKET_URL` / `CLAWCHAT_WS_URL`, `CLAWCHAT_BASE_URL`, `CLAWCHAT_TOKEN`, `CLAWCHAT_USER_ID`, `CLAWCHAT_REPLY_MODE`, `CLAWCHAT_GROUP_MODE`, `CLAWCHAT_MEDIA_LOCAL_ROOTS` — override `platforms.clawchat.extra` at hermes-agent startup (via the `env_overrides` patch).
- `CLAWCHAT_ALLOWED_USERS`, `CLAWCHAT_ALLOW_ALL_USERS` — auth allowlist, read by hermes-agent.
