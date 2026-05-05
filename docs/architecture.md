# Architecture

## What this repo is

A **Hermes Agent plugin** that integrates the ClawChat messaging platform. On Hermes v0.12.0+ it is loaded like any other plugin and registers the `clawchat` gateway platform through `ctx.register_platform(...)`; no Hermes source patch is required. The legacy anchor-patch installer is kept only for older Hermes builds that do not expose the platform registry API.

The package `clawchat_gateway` is also pip-installable (`pyproject.toml` → `[project] name = "clawchat-gateway"`), with a `clawchat-gateway-install` console script.

## Boot sequence

1. Hermes loads the repo root as a plugin and calls `register(ctx)` in `__init__.py`.
2. `_register_python_path(src)` inserts `src/` onto `sys.path` and drops a `clawchat_gateway_src.pth` file in a writable site-packages dir so subprocess Pythons also find the package.
3. `_register_platform(ctx)` calls `ctx.register_platform(...)` with the ClawChat adapter factory, config validation hooks, allowlist env vars, and platform prompt hint. If the platform registry API is not available, `register(ctx)` falls back to `_install_gateway()` for legacy Hermes builds.
4. `_configure_runtime_defaults()` seeds ClawChat allow-all / streaming defaults in `$HERMES_HOME`.
5. `_register_tools(ctx)` registers seven tools:
   - `clawchat_activate` — exchange an activation code for ClawChat credentials.
   - `clawchat_get_account_profile` — fetch the configured account profile.
   - `clawchat_get_user_profile` — fetch a public profile by explicit `userId`.
   - `clawchat_list_account_friends` — list friends with pagination.
   - `clawchat_update_account_profile` — update nickname, avatar URL, and/or bio.
   - `clawchat_upload_avatar_image` — upload a local avatar image and return a hosted URL.
   - `clawchat_upload_media_file` — upload a local media/file attachment and return a ClawChat media render URL.
6. `ctx.register_skill("clawchat", skills/clawchat/SKILL.md)` attaches the skill.

## Runtime data flow

```
Hermes LLM  <---- tool results ----  _handle_clawchat_* handlers  (in __init__.py)
    |                                        ^
    v                                        |
  (platform: CLAWCHAT)              clawchat_gateway.activate / tools / profile
    |
    v
ClawChatAdapter ----send----> ClawChatConnection (WebSocket)  <----> ClawChat server
  ^  ^
  |  |  Inbound `message.send` frames
  |  +---- parse_inbound_message (inbound.py) ---- build MessageEvent
  +------- handle_message (from BasePlatformAdapter, provided by hermes-agent)
```

- **Outbound** send: `adapter.send()` → optional `compute_delta` (stream_buffer) → `protocol.build_message_*` → `ClawChatConnection.send_frame()` → WebSocket.
- **Inbound** message: WebSocket → `ClawChatConnection._read_loop` → `_dispatch_inbound` → `adapter._on_message` → `parse_inbound_message` → `adapter._handle_inbound` → `handle_message` (hermes-agent dispatches to the LLM).
- **Run lifecycle**: Hermes v0.12+ calls adapter lifecycle hooks registered through the platform registry. `adapter.on_run_complete` emits `message.done` + final `message.reply` after LLM streaming finishes. Legacy patched installs wire the same method through the `post_stream_hook` / `normal_stream_done_hook` insertions.
- **Media**: inbound media URLs are downloaded by `media_runtime.download_inbound_media`; outbound local files from Hermes `MEDIA:` delivery are uploaded via `upload_outbound_media`. Local path roots are unrestricted by default, matching Hermes platform adapters; `media_local_roots` / `CLAWCHAT_MEDIA_LOCAL_ROOTS` can be set explicitly to tighten that policy.

## Key design choices

- **Platform registry first.** Hermes v0.12+ provides `ctx.register_platform(...)`, so ClawChat registers its adapter, validation hooks, auth env vars, and platform prompt without modifying Hermes source.
- **Legacy anchor-patch fallback.** `install.py` still inserts named blocks into hermes-agent source files for older Hermes builds without `ctx.register_platform`. Each block is wrapped with `# clawchat-gateway:<id>:start/end` markers for idempotency and clean uninstall.
- **`gateway.*` is imported at runtime, stubbed in tests.** Production adapter code imports `gateway.platforms.base.BasePlatformAdapter`; in tests `conftest.py` pre-registers stubs from `tests/fake_hermes.py` so the package can be imported without a real hermes-agent checkout.
- **Two supported WebSocket paths.** If the WebSocket URL path is `/v1/ws`, the legacy hello/challenge handshake is skipped (realtime subprotocol). Otherwise the adapter does a `connect` frame with HMAC `sign` over `client_id|nonce` and waits for `hello-ok`.
- **Streaming with deltas.** `stream_buffer.compute_delta(prev, curr)` produces the appended chunk so `message.add` carries only the delta. If the new text isn't a prefix-extension of the previous, the full text is resent.
- **Filter-before-send.** Adapter strips `<think>...</think>` blocks and tool-invocation fence/tag blocks out of visible output unless `show_think_output` / `show_tools_output` are explicitly enabled.
- **Activation self-restart.** After `clawchat_activate` writes `CLAWCHAT_TOKEN` / `CLAWCHAT_REFRESH_TOKEN` to `~/.hermes/.env` and non-secret platform settings to `~/.hermes/config.yaml`, the handler schedules a detached `sh -lc 'sleep 2; hermes gateway restart'` so the tool response can return before the gateway reloads.

## Environment variables

Runtime (read by Hermes v0.12+ platform registration helpers, the ClawChat Python modules here, and by legacy installed patches):

- `HERMES_HOME` — Hermes data dir (default `~/.hermes`). Controls `config.yaml`, `.env`, `skills/`, `plugins/` locations.
- `HERMES_DIR` / `HERMES_AGENT_DIR` — hermes-agent install dir (default `$HERMES_HOME/hermes-agent`, or `/opt/hermes` if present).
- `CLAWCHAT_WEBSOCKET_URL` / `CLAWCHAT_WS_URL`, `CLAWCHAT_BASE_URL`, `CLAWCHAT_TOKEN`, `CLAWCHAT_REFRESH_TOKEN`, `CLAWCHAT_USER_ID`, `CLAWCHAT_REPLY_MODE`, `CLAWCHAT_GROUP_MODE`, `CLAWCHAT_MEDIA_LOCAL_ROOTS` — override values in `platforms.clawchat.extra`; legacy patch installs inject the same values through the `env_overrides` blocks.
- `CLAWCHAT_ALLOWED_USERS`, `CLAWCHAT_ALLOW_ALL_USERS` — auth allowlist. The platform registration advertises these env vars to Hermes; `install.py` / `_configure_runtime_defaults()` set `CLAWCHAT_ALLOW_ALL_USERS=true` by default.
- `CLAWCHAT_DEVICE_ID` — override the auto-derived device id.
