# Plugin Tools — `clawchat_gateway/plugin_tools.py`

Hermes-facing tool registration and JSON-string result adapters for the ClawChat plugin.

## Helpers

| Function | Purpose |
|---|---|
| `_tool_error(exc)` | Shape activation exceptions as `{"ok": false, "error": "...", "kind": "..."}`. |
| `_tool_result(payload)` | Serialize a tool payload with `json.dumps(..., ensure_ascii=False)` for Hermes v0.12-compatible string results. |
| `_optional_int_arg(value)` | Normalize optional pagination args from schema input before passing them to `clawchat_gateway.tools`. |
| `_direct_tool_description(description)` | Append the direct-tool boundary that tells the LLM not to fall back to `execute`, shell scripts, curl, or direct HTTP calls. |

## Handlers

Each handler is `async`, takes `(args: dict, **kw)`, logs `task_id`, and returns a JSON string. The account/profile/media handlers delegate to `clawchat_gateway.tools`, which owns REST validation and error envelopes.

| Handler | Args | Backing |
|---|---|---|
| `handle_clawchat_activate` | `code`, optional `baseUrl` | `clawchat_gateway.activate.activate_and_maybe_restart(..., restart=True)` |
| `handle_clawchat_get_account_profile` | — | `clawchat_gateway.tools.get_account_profile` |
| `handle_clawchat_get_user_profile` | `userId` | `clawchat_gateway.tools.get_user_profile` |
| `handle_clawchat_list_account_friends` | optional `page`, optional `pageSize` | `clawchat_gateway.tools.list_account_friends` |
| `handle_clawchat_update_account_profile` | optional `nickname`, optional `avatar_url`, optional `bio` (>=1) | `clawchat_gateway.tools.update_account_profile` |
| `handle_clawchat_upload_avatar_image` | `filePath` | `clawchat_gateway.tools.upload_avatar_image` |
| `handle_clawchat_upload_media_file` | `filePath` | `clawchat_gateway.tools.upload_media_file` |

## Registration

`register_tools(ctx)` registers seven tools with fixed JSON schemas. The `name` inside each schema matches the registration key. Description text is intentionally prescriptive because it is surfaced to the LLM:

- `clawchat_activate` — exchange an activation code for credentials.
- `clawchat_get_account_profile` — fetch the configured account profile.
- `clawchat_get_user_profile` — fetch a public profile by explicit `userId`.
- `clawchat_list_account_friends` — list account friends with pagination.
- `clawchat_update_account_profile` — update nickname, avatar URL, and/or bio.
- `clawchat_upload_avatar_image` — upload a local avatar image and return its URL.
- `clawchat_upload_media_file` — upload a local file/media attachment and return its URL.

`register(ctx)` in the repo-root `__init__.py` imports this module lazily and calls `register_tools(ctx)` after platform registration and runtime defaults.
