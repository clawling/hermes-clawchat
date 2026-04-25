# Tests — `tests/`

Pytest-asyncio with `asyncio_mode = "auto"` (from `pyproject.toml`), so async tests do not need `@pytest.mark.asyncio`. Run with `pytest`, or target a single file/test (`pytest tests/test_adapter.py::test_name`).

## Harness

### `tests/conftest.py`

Inserts `src/` onto `sys.path`, then calls `fake_hermes.install()` to register stub modules for `gateway`, `gateway.config`, `gateway.platforms`, `gateway.platforms.base`. Every test file pulls in this harness automatically.

### `tests/fake_hermes.py` — hermes-agent stubs

Provides in-process replacements so the adapter can be imported without a real hermes-agent checkout:

- `_Platform` enum (`CLAWLING`, `QQBOT`, `CLAWCHAT`).
- `_MessageType` enum (`TEXT`, `IMAGE`).
- `_SessionSource` dataclass (`platform`, `chat_id`, `user_id`, `chat_name`, `chat_type`, `thread_id`).
- `_MessageEvent` dataclass (all the fields the adapter sets: `text`, `source`, `raw_message`, `media_urls`, `media_types`, `reply_to_message_id`, `reply_to_text`, `auto_skill`, `channel_prompt`, `timestamp`).
- `_SendResult` dataclass.
- `_BasePlatformAdapter` base class with `build_source()` and `handle_message()` — the test subclass's `handled: list[_MessageEvent]` records everything the adapter would have dispatched to hermes-agent.
- `install()` — writes the stub module objects into `sys.modules` so `from gateway.platforms.base import BasePlatformAdapter` resolves here.

When you add a new import from `gateway.*` in production code, extend `fake_hermes.py` or tests will fail at import time.

### `tests/fake_ws.py` — in-memory WebSocket peer

- `_ConnectionBuffers` — `client_outbox` / `server_outbox` asyncio queues + a `closed` flag.
- `FakeClientConnection` — implements `send`, `close`, `ping`, `__aiter__`/`__anext__` over the buffers. `None` put on `server_outbox` signals close.
- `FakeClawChatServer`:
  - `async connect(url, **kwargs)` — push a new `_ConnectionBuffers`, return a `FakeClientConnection`. Patched into `connection._ws_connect_impl` by tests.
  - `enqueue_from_server(frame, *, connection_index=-1)` — push a server → client frame.
  - `async read_client_frame(timeout=1.0, *, connection_index=-1)` — pop a client → server frame.
  - `async disconnect(*, connection_index=-1)` — close the peer.
  - `set_auto_fail(value)` — next `connect` raises `ConnectionError("fake auto-fail")`, for backoff tests.
  - `connect_calls` — log of every `connect(url, kwargs)` invocation.

## Test files

### `tests/test_activate.py`

- `test_persist_activation_writes_clawchat_config` — monkeypatches `$HERMES_HOME`; calls `activate.persist_activation` and checks that `config.yaml` has `platforms.clawchat.enabled`, the expected `extra` keys, and streaming/display defaults.

### `tests/test_adapter.py` (~30 tests)

Uses a `FakeConnection` stand-in so no WebSocket I/O is performed. Coverage:

- `compute_delta` behaviour for append and reset cases.
- `_on_message` — builds `MessageEvent`, attaches the `clawchat` skill on activation-intent text, downloads media before dispatch, logs inbound parse / dispatch, logs parse drops, maps `reply_preview` fields.
- `send` — static mode (`message.reply`); default filtering of `<think>` and tool output; override via `show_*_output`; suppression and preservation of gateway tool-progress tickers (both for `send` and `edit_message`); logging.
- Typing indicators — active / inactive / dedupe.
- Streaming mode — `message.created` → `message.add` sequence, incomplete-block filtering before delta; `edit_message` delta emission; targeting by `message_id` when multiple runs overlap; `on_run_complete` emits `message.done` + `message.reply` and finalises the requested run during overlap.
- `edit_message` finalize semantics — `finalize=True` flushes the delta and then emits `message.done` + `message.reply` via `on_run_complete`; unknown kwargs from newer hermes-agent stream consumers are swallowed without raising `TypeError`.
- Outbound media — forces static mode when media is present; classifies non-image MIME correctly; uploads local files before the static reply; `send_image_file` path.

### `tests/test_api_client.py`

Uses a local `BaseHTTPRequestHandler` fixture (`api_server`) to verify:

- `agents_connect` posts the fixed `{platform, type}` body and honours optional `tools` list.
- `upload_media` sends multipart with a Bearer token to `/media/upload`.
- `upload_avatar` uses `/v1/files/upload-url`.
- `update_my_profile` PATCHes `/v1/users/me`.
- Constructor validation rejects a non-http scheme.

### `tests/test_config.py`

- `test_config_defaults` — `ClawChatConfig.from_platform_config` with an empty extra falls back to every documented default.
- `test_config_accepts_nested_openclaw_names` — verifies both snake_case and camelCase alias lookups.

### `tests/test_connection.py`

Patches `connection._ws_connect_impl` with `FakeClawChatServer.connect` and exercises the full state machine:

- Legacy handshake reaches `READY` (challenge → connect → hello-ok).
- Realtime subprotocol (`/v1/ws`) skips the handshake.
- `message.send` is ignored before `READY`.
- Bearer auth header is present on connect.
- Correct subprotocols are sent.
- Wrong `request_id` in hello-ok times out.
- Outbound frames queued before `READY` flush in order after `READY`.
- Connection logs receive / dispatch / send at the info level.
- Ready transition preserves queued frame ordering.
- Queued frames survive a failed flush + reconnect.
- A send failure while `READY` re-queues for the next connection.
- Backoff progresses both for repeated `connect` failures and for flapping `READY` sessions shorter than `BACKOFF_RESET_AFTER_SECONDS`.

### `tests/test_device_id.py`

- `CLAWCHAT_DEVICE_ID` env override sanitises / passes through the `hermes-` prefix.
- macOS path uses `ioreg`'s `IOPlatformUUID` output.
- LRU cache across tests is cleared by the fixture (via `monkeypatch`).

### `tests/test_git_plugin.py`

Imports the repo-root `__init__.py` via a dummy `_Ctx` context and verifies:

- `register(ctx)` adds three tools and a skill.
- Tool handlers accept and echo `task_id`.

### `tests/test_inbound.py`

Matrix of `parse_inbound_message` edge cases:

- Group-mode `mention` requires the bot to be mentioned.
- `reply_preview` passes through.
- Group-mode `mention` accepts when mentioned; group-mode `all` accepts without mention.
- Mixed text + media fragments produce Markdown placeholders and populate `media_urls`.
- `message.body` as string, dict, and list of `{type, content}` fragments.
- Truthy-but-non-dict `payload`, `message`, `context`, `sender` all return `None`.

### `tests/test_install.py`

- `test_build_patches_contains_expected_ids` — all 16 named patches are present (including the two `cron_*` patches).
- `test_apply_and_remove_patch_with_indentation` — indentation is preserved and removal is idempotent.
- `test_cli_platform_registry_patch_inserts_clawchat` — specific check for the CLI registry patch.
- `test_cron_scheduler_patches_insert_clawchat` — verifies `cron_known_delivery_platforms` and `cron_platform_map` insert ClawChat into hermes-agent's `cron/scheduler.py` allowlist and platform map so `deliver=clawchat:<chat_id>` cron jobs aren't dropped at the unknown-platform branch.
- `test_install_state_round_trip` — state file write/read.
- `test_install_and_uninstall_skill` — installs the skill, removes the legacy plugin dir, round-trips uninstall.
- `test_install_rolls_back_when_anchor_missing` — fabricates a hermes-agent tree where one anchor is missing, runs `main(...)`, and asserts the run exits non-zero, prints `error: "failed_to_apply_some_patches"` with a `rolled_back` list, and leaves no `clawchat-gateway:` markers in any file (atomic install).
- `test_package_init_does_not_eagerly_import_adapter` — imports `clawchat_gateway` and `clawchat_gateway.install` and asserts `clawchat_gateway.adapter` is **not** in `sys.modules`. Regression test for the bug where re-exporting `ClawChatAdapter` from the package init forced adapter to bind a stale `Platform` enum before the patch ran.
- `configure_clawchat_allow_all` — writes + updates `$HERMES_HOME/.env`.
- `clear_skills_prompt_snapshot`.
- `configure_clawchat_streaming` — writes a full config.yaml skeleton with the expected defaults.

### `tests/test_media_runtime.py`

- `infer_media_kind_from_mime` — normal cases + MIME parameters and casing.
- `ensure_allowed_local_path` — under-roots pass, outside-roots fail, empty roots fail closed, nested roots accepted.
- `derive_base_url` — prefers WebSocket origin; falls back to WebSocket origin when base is missing.
- `upload_outbound_media` — uploads local paths; skips a single failing item while proceeding with the rest.
- `download_inbound_media` — resolves relative URLs against the WebSocket origin and writes a local file.

### `tests/test_profile.py`

Spins up an `api_server` fixture; covers:

- `update_nickname` loads `$HERMES_HOME/config.yaml` and PATCHes `/v1/users/me` with the nickname.
- `update_avatar` uploads via `/v1/files/upload-url` then PATCHes the profile with the returned URL.
- `load_profile_config` raises when the token is missing.
- `update_avatar` rejects relative local paths.

### `tests/test_protocol.py`

Frame-builder unit tests:

- `compute_client_sign` outputs lower-hex.
- `new_frame_id` uses the expected prefixed UUID shape.
- `build_connect_request` emits the realtime `connect` event with token/client/sign.
- `build_message_add_event` carries `full_text` and `delta`.
- `build_message_done_event` matches the v2 streaming payload shape.
- `build_message_reply_event` includes reply context when `reply_to_message_id` is present.
- `build_typing_update_event` shape.
- `extract_nonce` returns `None` for non-dict payload / non-dict `payload.data`; reads the nested data nonce.
- `is_hello_ok` rejects non-dict payloads and wrong payload type; accepts the realtime event form.
