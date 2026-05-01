# Architecture

## What this repo is

A **Hermes Agent plugin** that integrates the ClawChat messaging platform. Loaded into a running hermes-agent process; on first install, it patches hermes-agent source files to register a new `CLAWCHAT` platform.

The package `clawchat_gateway` is also pip-installable (`pyproject.toml` → `[project] name = "clawchat-gateway"`), with a `clawchat-gateway-install` console script.

## Boot sequence

1. Hermes loads the repo root as a plugin and calls `register(ctx)` in `__init__.py`.
2. `_register_python_path(src)` inserts `src/` onto `sys.path` and drops a `clawchat_gateway_src.pth` file in a writable site-packages dir so subprocess Pythons also find the package.
3. `_register_tools(ctx)` registers seven tools:
   - `clawchat_activate` — exchange an activation code for ClawChat credentials.
   - `clawchat_get_account_profile` — fetch the configured account profile.
   - `clawchat_get_user_profile` — fetch a public profile by explicit `userId`.
   - `clawchat_list_account_friends` — list friends with pagination.
   - `clawchat_update_account_profile` — update nickname, avatar URL, and/or bio.
   - `clawchat_upload_avatar_image` — upload a local avatar image and return a hosted URL.
   - `clawchat_upload_media_file` — upload a local media/file attachment and return a public URL.
4. `ctx.register_skill("clawchat", skills/clawchat/SKILL.md)` attaches the skill.
5. `_install_gateway()` invokes `clawchat_gateway.install.main(["--hermes-dir", ...])`, which anchor-patches hermes-agent's source files (idempotent). Failures are logged but do not abort plugin load.

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
- **Run lifecycle**: hermes-agent calls `adapter.on_run_complete` after LLM streaming finishes, which emits `message.done` + final `message.reply`. This hook is wired up by the `post_stream_hook` and `normal_stream_done_hook` patches.
- **Media**: inbound media URLs are downloaded by `media_runtime.download_inbound_media`; outbound media is uploaded via `upload_outbound_media`, which enforces `media_local_roots` for local paths.

## Key design choices

- **Anchor-patch installer.** Because hermes-agent has no pluggable platform API, `install.py` inserts named blocks into hermes-agent's own source files by matching `anchor` strings. Each block is wrapped with `# clawchat-gateway:<id>:start/end` markers for idempotency and clean uninstall.
- **`gateway.*` is imported at runtime, stubbed in tests.** Production adapter code imports `gateway.platforms.base.BasePlatformAdapter`; in tests `conftest.py` pre-registers stubs from `tests/fake_hermes.py` so the package can be imported without a real hermes-agent checkout.
- **Two supported WebSocket paths.** If the WebSocket URL path is `/v1/ws`, the legacy hello/challenge handshake is skipped (realtime subprotocol). Otherwise the adapter does a `connect` frame with HMAC `sign` over `client_id|nonce` and waits for `hello-ok`.
- **Streaming with deltas.** `stream_buffer.compute_delta(prev, curr)` produces the appended chunk so `message.add` carries only the delta. If the new text isn't a prefix-extension of the previous, the full text is resent.
- **Filter-before-send.** Adapter strips `<think>...</think>` blocks and tool-invocation fence/tag blocks out of visible output unless `show_think_output` / `show_tools_output` are explicitly enabled.
- **Activation self-restart.** After `clawchat_activate` writes `CLAWCHAT_TOKEN` / `CLAWCHAT_REFRESH_TOKEN` to `~/.hermes/.env` and non-secret platform settings to `~/.hermes/config.yaml`, the handler schedules a detached `sh -lc 'sleep 2; hermes gateway restart'` so the tool response can return before the gateway reloads.

## Environment variables

Runtime (read by installed hermes-agent patches and by Python modules here):

- `HERMES_HOME` — Hermes data dir (default `~/.hermes`). Controls `config.yaml`, `.env`, `skills/`, `plugins/` locations.
- `HERMES_DIR` / `HERMES_AGENT_DIR` — hermes-agent install dir (default `$HERMES_HOME/hermes-agent`, or `/opt/hermes` if present).
- `CLAWCHAT_WEBSOCKET_URL` / `CLAWCHAT_WS_URL`, `CLAWCHAT_BASE_URL`, `CLAWCHAT_TOKEN`, `CLAWCHAT_REFRESH_TOKEN`, `CLAWCHAT_USER_ID`, `CLAWCHAT_REPLY_MODE`, `CLAWCHAT_GROUP_MODE`, `CLAWCHAT_MEDIA_LOCAL_ROOTS` — inject values into `platforms.clawchat.extra` at hermes-agent startup (via the `env_overrides` patches in `install.py`).
- `CLAWCHAT_ALLOWED_USERS`, `CLAWCHAT_ALLOW_ALL_USERS` — auth allowlist (read by hermes-agent; `install.py` sets the latter to `true` by default).
- `CLAWCHAT_DEVICE_ID` — override the auto-derived device id.
