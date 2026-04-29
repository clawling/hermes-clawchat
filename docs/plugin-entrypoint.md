# Plugin Entrypoint

Covers the repo-root `__init__.py`, `plugin.yaml`, and `src/clawchat_gateway/__init__.py`.

## `plugin.yaml`

Hermes plugin manifest.

```yaml
manifest_version: 1
name: clawchat
version: 0.1.0
description: "ClawChat gateway integration for Hermes Agent."
author: NewBase
provides_hooks: []
provides_tools: []
```

The actual tools are registered dynamically via `ctx.register_tool` in `register()`, not declared statically here.

## Repo-root `__init__.py`

### Path helpers

| Function | Signature | Purpose |
|---|---|---|
| `_plugin_dir` | `() -> Path` | Absolute path of this file's parent directory. |
| `_hermes_dir` | `() -> Path` | Resolve hermes-agent dir from `HERMES_DIR` / `HERMES_AGENT_DIR`; fall back to `/opt/hermes` if `/opt/hermes/gateway` exists, else `$HERMES_HOME/hermes-agent`. |
| `_register_python_path` | `(src: Path) -> None` | Prepend `src` to `sys.path` **and** write `clawchat_gateway_src.pth` into the first writable site-packages so child Pythons also import the package. Raises `RuntimeError` if no writable dir is found. |
| `_install_gateway` | `() -> None` | Call `clawchat_gateway.install.main(["--hermes-dir", ...])`; raise `RuntimeError` on non-zero exit. |

### Tool error shaping

| Function | Signature | Purpose |
|---|---|---|
| `_tool_error` | `(exc: Exception) -> dict` | Return `{"ok": False, "error": str(exc), "kind": exc.__class__.__name__}`. |

### Tool handlers

Each handler is `async`, takes `(args: dict, **kw)`, logs `task_id`, and returns a dict. `clawchat_activate` still uses `_tool_error(exc)` for legacy activation failures. The six account/media handlers delegate to `clawchat_gateway.tools` and return that module's result envelope directly.

| Handler | Args | Backing |
|---|---|---|
| `_handle_clawchat_activate` | `code`, optional `baseUrl` | `clawchat_gateway.activate.activate` |
| `_handle_clawchat_get_account_profile` | — | `clawchat_gateway.tools.get_account_profile` |
| `_handle_clawchat_get_user_profile` | `userId` | `clawchat_gateway.tools.get_user_profile` |
| `_handle_clawchat_list_account_friends` | optional `page`, optional `pageSize` | `clawchat_gateway.tools.list_account_friends` |
| `_handle_clawchat_update_account_profile` | optional `nickname`, optional `avatar_url`, optional `bio` (>=1) | `clawchat_gateway.tools.update_account_profile` |
| `_handle_clawchat_upload_avatar_image` | `filePath` | `clawchat_gateway.tools.upload_avatar_image` |
| `_handle_clawchat_upload_media_file` | `filePath` | `clawchat_gateway.tools.upload_media_file` |

### Tool registration

`_register_tools(ctx)` registers seven tools with fixed JSON schemas. The `name` inside each schema matches the registration key. Description text is intentionally prescriptive because it is surfaced to the LLM:

- `clawchat_activate` (🔑) — exchange an activation code for credentials.
- `clawchat_get_account_profile` (👤) — fetch the configured account profile.
- `clawchat_get_user_profile` (🧑) — fetch a public profile by explicit `userId`.
- `clawchat_list_account_friends` (👥) — list account friends with pagination.
- `clawchat_update_account_profile` (✏️) — update nickname, avatar URL, and/or bio.
- `clawchat_upload_avatar_image` (🖼️) — upload a local avatar image and return its URL.
- `clawchat_upload_media_file` (📎) — upload a local file/media attachment and return its URL.

### `register(ctx)` — plugin entrypoint

Order of operations:

1. `_register_python_path(_plugin_dir() / "src")`
2. `_install_gateway()` applies the hermes-agent patches.
3. `_register_tools(ctx)`
4. If `skills/clawchat/SKILL.md` exists, `ctx.register_skill("clawchat", skill, description=...)`.

## `src/clawchat_gateway/__init__.py`

Public package surface:

The package `__init__` intentionally exposes only `__version__`. It does not eagerly import `adapter.py`, because that module binds hermes-agent's `gateway.config.Platform` at import time and must only be loaded after the plugin has applied its platform patch.
