# ClawChat Tools Parity for `hermes-clawchat`

Date: 2026-04-29
Status: Draft

## 1. Goal

Bring `hermes-clawchat`'s ClawChat tool surface in line with the
`openclaw-clawchat` reference implementation. After this change, both plugins
expose the same six `clawchat_*` tools backed by the same REST endpoints, with
the same error envelope. Hermes additionally keeps `clawchat_activate` because
Hermes has no equivalent of OpenClaw's channel-login activation path.

Out-of-scope this phase: `skills/clawchat/SKILL.md` and `docs/skill.md`. The
LLM-facing skill prompt is owned by a separate workstream and is not touched
here.

## 2. Final tool surface

7 tools total. The 6 new tools mirror the openclaw spec:

| Tool | Backend | Notes |
|---|---|---|
| `clawchat_activate` | `POST /v1/agents/connect` | unchanged |
| `clawchat_get_account_profile` | `GET /v1/users/me` | new |
| `clawchat_get_user_profile` | `GET /v1/users/{userId}` | new — `userId` required, no nickname inference |
| `clawchat_list_account_friends` | `GET /v1/friends?page=&pageSize=` | new — defaults `page=1`, `pageSize=20`, range `1..100` |
| `clawchat_update_account_profile` | `PATCH /v1/users/me` | new — at least one of `nickname` / `avatar_url` / `bio` |
| `clawchat_upload_avatar_image` | `POST /v1/files/upload-url` | new — upload-only, returns URL, **does not** auto-update profile |
| `clawchat_upload_media_file` | `POST /media/upload` | new — upload-only, returns URL, **not** for avatar updates |

Removed:

- `clawchat_update_nickname`
- `clawchat_update_avatar`

These two are subsumed by `clawchat_update_account_profile` +
`clawchat_upload_avatar_image`. The two-step flow (upload, then PATCH) is
explicit on the new surface and matches openclaw.

## 3. Architecture

### 3.1 Components

```
hermes-clawchat/
├── __init__.py                          (modified: re-wire register_tool calls)
├── src/clawchat_gateway/
│   ├── api_client.py                    (unchanged — already exposes all 6 backends)
│   ├── tools.py                         (NEW — 6 async tool handlers, error mapping)
│   └── profile.py                       (CLI rewritten; legacy update_nickname/avatar removed)
├── tests/
│   ├── test_tools.py                    (NEW — handler-level coverage)
│   └── test_profile.py                  (rewritten — new CLI subcommands)
└── docs/
    ├── architecture.md                  (refreshed tool list)
    ├── plugin-entrypoint.md             (refreshed handler table + tool list)
    ├── profile.md                       (rewritten around new CLI)
    └── tests.md                         (refreshed)
```

`README.md`, `CLAUDE.md`, `dev_install.md`, `install.md` also touched (text
references to the old tool/CLI names).

### 3.2 Tool handler module — `src/clawchat_gateway/tools.py`

Single source of truth for the 6 new tools. Each handler:

1. Loads config via `clawchat_gateway.profile.load_profile_config()`. If the
   config file is missing, or `token` / `user_id` are absent, return:

   ```json
   { "error": "config", "message": "..." }
   ```

   No HTTP request is fired.

2. Validates inputs locally. On failure return:

   ```json
   { "error": "validation", "message": "..." }
   ```

   No HTTP request is fired.

3. Calls `ClawChatApiClient`. On success, returns the envelope `data` payload
   directly (preserving openclaw's behavior of "return backend `data`").

4. On `ClawChatApiError`, maps `err.kind` 1:1 to the error envelope:

   | `err.kind` | output `error` |
   |---|---|
   | `validation` | `validation` |
   | `auth` (HTTP 401/403) | `auth` |
   | `api` (envelope `code != 0`) | `api` |
   | `transport` (network / non-2xx / non-JSON / missing `code`) | `transport` |

   Plus `unknown` for unexpected exceptions.

The `meta` field is included only when `ClawChatApiError` carries non-empty
metadata (e.g. `status`, `path`, `code`).

### 3.3 `__init__.py` rewire

- Remove `_handle_clawchat_update_nickname`, `_handle_clawchat_update_avatar`,
  and their two `ctx.register_tool` calls.
- Add 6 new `_handle_clawchat_*` thin wrappers that delegate to
  `clawchat_gateway.tools`. Each wrapper logs `task_id` (matching existing
  pattern) and returns the handler's result dict directly.
- Each `register_tool` call uses a JSON-Schema dict whose shape mirrors
  `tools-schema.ts` from openclaw, and whose `description` field is adapted
  from openclaw's `tools.ts` trigger-rich English+Chinese phrasing (since the
  LLM-facing prompt is the part that decides whether a tool fires).
- `clawchat_activate` registration is unchanged.

### 3.4 CLI rewrite — `python -m clawchat_gateway.profile`

Replace `nickname` / `avatar` subcommands with subcommands mirroring the new
tool surface. Each subcommand calls the *same* handler the tool calls (single
source of truth).

| Subcommand | Args | Backing handler |
|---|---|---|
| `get` | — | `tools.get_account_profile()` |
| `get-user <userId>` | userId (positional) | `tools.get_user_profile(userId)` |
| `friends [--page N] [--page-size N]` | both optional | `tools.list_account_friends(page, page_size)` |
| `update [--nickname X] [--avatar-url URL] [--bio X]` | ≥1 required | `tools.update_account_profile(...)` |
| `upload-avatar <path>` | absolute local path | `tools.upload_avatar_image(path)` |
| `upload-media <path>` | absolute local path | `tools.upload_media_file(path)` |

CLI:

- Handlers in `tools.py` return result dicts; they do not raise. The CLI
  inspects `result.get("error")` to choose its output stream and exit code.
- On success (no `"error"` key): prints handler result as pretty JSON to
  stdout, exits 0.
- On error (any `"error"` key): prints handler result (already shaped as
  `{"error": "...", "message": "...", "meta?": ...}`) as pretty JSON to
  stderr, exits 1.

The legacy `nickname` and `avatar` subcommands are removed without aliasing.
This is a breaking change for any local dev script that called them; that
trade-off is accepted because the spec describes a clean replacement.

### 3.5 Error envelope (uniform across tools and CLI)

```json
{
  "error": "config|validation|auth|api|transport|unknown",
  "message": "...",
  "meta": { "status": 401, "path": "/v1/users/me", "code": 7 }
}
```

`meta` is omitted when there's nothing useful to attach.

### 3.6 Validation rules

- `clawchat_get_user_profile`: `userId` is a non-empty string.
- `clawchat_list_account_friends`: integers; defaults `page=1`, `pageSize=20`;
  range `page >= 1`, `1 <= pageSize <= 100`. Out-of-range is a `validation`
  error (not silently clamped — matches openclaw's zod schema).
- `clawchat_update_account_profile`: at least one of `nickname` /
  `avatar_url` / `bio` must be a string. None present →
  `validation`.
- `clawchat_upload_avatar_image` / `clawchat_upload_media_file`: `filePath`
  must be:
  - a non-empty string,
  - an absolute path,
  - existing,
  - a regular file,
  - non-empty,
  - `<= 20 MB` (`MAX_UPLOAD_BYTES = 20 * 1024 * 1024`).

  Any failure → `validation`, no HTTP request.

### 3.7 HTTP client behavior (unchanged)

`api_client.py` already implements the wire contract:

- Headers: `Authorization: Bearer <token>`, `X-Device-Id: <device-id>`,
  `Content-Type: application/json` for JSON bodies.
- Envelope: `{"code": 0, "data": {...}}` on success;
  `{"code": <non-zero>, "msg": "...", "data": ...}` on business error.
- HTTP 401/403 → `ClawChatApiError(kind="auth")`.
- Envelope `code != 0` → `ClawChatApiError(kind="api")`.
- Network / non-JSON / missing numeric `code` → `ClawChatApiError(kind="transport")`.

No changes to this module are required.

## 4. Tests

### 4.1 New: `tests/test_tools.py`

For each of the 6 new tools, monkeypatch the underlying `ClawChatApiClient`
method (mirroring the pattern in the existing `tests/test_profile.py`).

| # | Case | Expected |
|---|---|---|
| 1 | Each tool, happy path with valid config | returns backend `data` dict |
| 2 | Config file missing | `{"error": "config", ...}`, no HTTP call |
| 3 | Config has no token / no user_id | `{"error": "config", ...}`, no HTTP call |
| 4 | `update_account_profile` with no fields | `{"error": "validation", ...}`, no HTTP call |
| 5 | Upload tools with relative path | `{"error": "validation", ...}`, no HTTP call |
| 6 | Upload tools with missing file | `{"error": "validation", ...}`, no HTTP call |
| 7 | Upload tools with > 20MB file | `{"error": "validation", ...}`, no HTTP call |
| 8 | Backend raises `ClawChatApiError(kind="auth")` | `{"error": "auth", ...}` |
| 9 | Backend raises `ClawChatApiError(kind="api", code=N)` | `{"error": "api", ..., "meta": {..., "code": N}}` |
| 10 | Backend raises `ClawChatApiError(kind="transport")` | `{"error": "transport", ...}` |
| 11 | `list_account_friends` with no params | invokes API with `page=1, pageSize=20` |
| 12 | `list_account_friends` with `pageSize=200` | `validation` error, no HTTP call |
| 13 | `get_user_profile` with empty `userId` | `validation` error, no HTTP call |

### 4.2 Rewritten: `tests/test_profile.py`

Drops nickname/avatar tool tests (the tools are gone). Keeps coverage for:

- `load_profile_config` (config absent / config malformed / config valid).
- Each new CLI subcommand: happy path + error path.

### 4.3 Untouched

`tests/test_activate.py`, `tests/test_adapter.py`, `tests/test_api_client.py`,
`tests/test_config.py`, `tests/test_connection.py`, `tests/test_device_id.py`,
`tests/test_git_plugin.py`, `tests/test_inbound.py`, `tests/test_install.py`,
`tests/test_media_runtime.py`, `tests/test_plugin.py`, `tests/test_protocol.py`.

## 5. Docs to update

| File | Change |
|---|---|
| `README.md` | Refresh tool list and any quickstart command referencing old names. |
| `CLAUDE.md` | Update "Common commands" CLI block (lines 34–35); update the "Plugin registration" sentence (line 44) to say "registers seven Hermes tools" and list them. |
| `dev_install.md` | Replace any `profile nickname` / `profile avatar` references. |
| `install.md` | Replace any `profile nickname` / `profile avatar` references. |
| `docs/architecture.md` | Refresh the tools list (currently mentions old names). |
| `docs/plugin-entrypoint.md` | Refresh the handler table and the tool list. |
| `docs/profile.md` | Rewrite around the new CLI subcommands. |
| `docs/tests.md` | Refresh test descriptions to match new tests. |

## 6. Out of scope (this phase)

- `skills/clawchat/SKILL.md` (LLM-facing prompt; out of scope per user).
- `docs/skill.md` (mirrors SKILL.md; out of scope).
- Any change to `api_client.py`, `adapter.py`, `connection.py`,
  `protocol.py`, `inbound.py`, `media_runtime.py`, `install.py`,
  `activate.py`, `restart.py`, `device_id.py`, or `stream_buffer.py`.

## 7. Acceptance criteria

- 7 tools registered after plugin load: `clawchat_activate` plus the 6 new
  ones. The 2 old tools no longer appear.
- Each of the 6 new tools, when invoked without config, returns
  `{"error": "config", ...}` and fires no HTTP request.
- Each new tool's happy path returns the backend `data` dict directly.
- `update_account_profile` with no fields returns `validation` error.
- Upload tools fail locally on relative / missing / oversized files; no HTTP
  request fired.
- HTTP 401/403 surfaces as `auth` error; `code != 0` surfaces as `api` error.
- The CLI's 6 subcommands work end-to-end via the same handlers.
- `pytest` passes (existing tests not regressed).
- Docs and README no longer reference the removed tool names.
