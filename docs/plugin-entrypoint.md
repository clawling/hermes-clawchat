# Plugin Entrypoint

Covers the repo-root `__init__.py`, `plugin.yaml`, and `src/clawchat_gateway/__init__.py`.

## `plugin.yaml`

Hermes plugin manifest.

```yaml
manifest_version: 1
name: clawchat
kind: platform
version: 0.1.0
description: "ClawChat gateway integration for Hermes Agent."
author: NewBase
requires_env:
  - CLAWCHAT_TOKEN
  - CLAWCHAT_REFRESH_TOKEN
provides_hooks: []
provides_tools:
  - clawchat_activate
  - clawchat_get_account_profile
  - clawchat_get_user_profile
  - clawchat_list_account_friends
  - clawchat_update_account_profile
  - clawchat_upload_avatar_image
  - clawchat_upload_media_file
```

The manifest declares that this is a gateway platform plugin and lists the tools surfaced by `register()`. The actual platform and tool handlers are still registered dynamically through the plugin context.

## Repo-root `__init__.py`

### Path helpers

| Function | Signature | Purpose |
|---|---|---|
| `_plugin_dir` | `() -> Path` | Absolute path of this file's parent directory. |
| `_hermes_dir` | `() -> Path` | Resolve hermes-agent dir from `HERMES_DIR` / `HERMES_AGENT_DIR`; fall back to `/opt/hermes` if `/opt/hermes/gateway` exists, else `$HERMES_HOME/hermes-agent`. |
| `_register_python_path` | `(src: Path) -> None` | Prepend `src` to `sys.path` **and** write `clawchat_gateway_src.pth` into the first writable site-packages so child Pythons also import the package. Raises `RuntimeError` if no writable dir is found. |
| `_install_gateway` | `() -> None` | Legacy fallback for Hermes builds without `ctx.register_platform`: call `clawchat_gateway.install.main(["--hermes-dir", ...])`; raise `RuntimeError` on non-zero exit. |

### Platform registration

Hermes v0.12.0+ loads ClawChat through the platform registry instead of source patches.

| Function | Signature | Purpose |
|---|---|---|
| `_clawchat_platform_config_with_home_extra` | `(config) -> PlatformConfig-like` | Merge sparse runtime config with `platforms.clawchat.extra` from `$HERMES_HOME/config.yaml`. |
| `_check_clawchat_platform_requirements` | `() -> bool` | Check optional runtime dependencies such as `websockets`. |
| `_validate_clawchat_platform_config` | `(config) -> bool` | Validate the merged ClawChat config has `websocket_url` and `token`. |
| `_create_clawchat_adapter` | `(config) -> ClawChatAdapter` | Build `ClawChatAdapter` with merged config. |
| `_register_platform` | `(ctx) -> bool` | If `ctx.register_platform` exists, register the `clawchat` platform with adapter factory, validation hooks, auth env vars, max message length, emoji, and platform hint. Returns `False` on older Hermes builds. |
| `_configure_runtime_defaults` | `() -> None` | Configure allow-all and streaming defaults without patching Hermes source. |

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
- `clawchat_upload_media_file` (📎) — upload a local file/media attachment and return its ClawChat media render URL.

### `register(ctx)` — plugin entrypoint

Order of operations:

1. `_register_python_path(_plugin_dir() / "src")`
2. `_register_platform(ctx)` registers `clawchat` through Hermes' platform registry on v0.12.0+.
3. If platform registration succeeds, `_configure_runtime_defaults()` seeds ClawChat defaults in `$HERMES_HOME`.
4. If platform registration is unavailable, `_install_gateway()` applies legacy hermes-agent patches.
5. `_register_tools(ctx)`
6. If `skills/clawchat/SKILL.md` exists, `ctx.register_skill("clawchat", skill, description=...)`.

## `src/clawchat_gateway/__init__.py`

Public package surface:

The package `__init__` intentionally exposes only `__version__`. It does not eagerly import `adapter.py`, because that module imports Hermes' `gateway.config.Platform` at module scope. Keeping the adapter import lazy avoids stale enum references in legacy patched installs and keeps modern platform registration from importing gateway modules before Hermes is ready.
