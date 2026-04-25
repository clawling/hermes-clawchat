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
| `_install_gateway` | `() -> None` | Call `clawchat_gateway.install.main(["--hermes-dir", ...])`; raise `RuntimeError` on non-zero exit, then `_refresh_gateway_module_cache()`. |
| `_refresh_gateway_module_cache` | `() -> None` | `importlib.invalidate_caches()` then reload any module in `_GATEWAY_MODULES_TO_REFRESH` (`gateway.config`, `gateway.run`, `clawchat_gateway.adapter`) that's already in `sys.modules`. Required because hermes-agent's CLI may have imported `gateway.config` before plugin discovery — without a reload, `Platform.CLAWCHAT` resolves against the pre-patch enum. |

### Tool error shaping

| Function | Signature | Purpose |
|---|---|---|
| `_tool_error` | `(exc: Exception) -> dict` | Return `{"ok": False, "error": str(exc), "kind": exc.__class__.__name__}`. |

### Gateway restart scheduling

| Function | Signature | Purpose |
|---|---|---|
| `_schedule_gateway_restart` | `(delay_seconds: int = 2) -> str` | Spawn detached `sh -lc 'sleep N; HERMES_HOME=... HERMES_DIR=... <hermes> gateway restart'`. Binary is looked up in `$HERMES_DIR/.venv/bin/hermes`, `~/.hermes/hermes-agent/.venv/bin/hermes`, `/opt/hermes/.venv/bin/hermes`, else `hermes` on PATH. Returns the constructed shell command for logging. |

### Tool handlers

Each handler is `async`, takes `(args: dict, **kw)`, and returns a dict (success path) or `_tool_error(exc)`. They all:
- read `kw.get("task_id")`,
- stash it on `handler._last_task_id` (for test observability),
- log start/done/failure.

| Handler | Args | Calls |
|---|---|---|
| `_handle_clawchat_activate` | `code` (required), `baseUrl` (optional) | `clawchat_gateway.activate.activate(code, base_url)`, then `_schedule_gateway_restart(2)`. Adds `ok`, `restart_scheduled`, `restart_delay_seconds`, `restart_message` to the result. |
| `_handle_clawchat_update_nickname` | `nickname` | `clawchat_gateway.profile.update_nickname(nickname)` |
| `_handle_clawchat_update_avatar` | `filePath` | `clawchat_gateway.profile.update_avatar(filePath)` |

### Tool registration

`_register_tools(ctx)` registers three tools with fixed JSON schemas. The `name` inside each schema matches the registration key. Description text is intentionally prescriptive — it's surfaced to the LLM and must stay aligned with `skills/clawchat/SKILL.md`:

- `clawchat_activate` (🔑) — emphasises "always use this when the user says a ClawChat activation code"; includes Chinese examples; tells the model not to call `connect-codes`.
- `clawchat_update_nickname` (🏷️)
- `clawchat_update_avatar` (🖼️) — emphasises that the tool uploads first via `/v1/files/upload-url`, then patches the profile; forbids HTTP URLs or relative paths.

### `register(ctx)` — plugin entrypoint

Order of operations:

1. `_register_python_path(_plugin_dir() / "src")`.
2. Try `_install_gateway()`. On `Exception`, log an error and **re-raise** — the auto-install must succeed before tools/skill register, otherwise hermes-agent could be left half-patched.
3. `_register_tools(ctx)`.
4. If `skills/clawchat/SKILL.md` exists, `ctx.register_skill("clawchat", skill, description=...)`.

## `src/clawchat_gateway/__init__.py`

Public package surface — kept deliberately minimal:

```python
__version__ = "0.1.0"
__all__ = ["__version__"]
```

Do **not** re-export `ClawChatAdapter` here. The adapter does `from gateway.config import Platform` at module scope, and the `platform_enum` install patch adds `Platform.CLAWCHAT` to that enum on disk. If anything imports `clawchat_gateway.adapter` before `register()` has applied the patch (for example, a stray `from clawchat_gateway import ClawChatAdapter` on the way to calling `clawchat_gateway.install.main`), the adapter binds a stale `Platform` reference and `super().__init__(..., Platform.CLAWCHAT)` raises `AttributeError` even after `gateway.config` is reloaded. Consumers should always import via the submodule path: `from clawchat_gateway.adapter import ClawChatAdapter`.

`tests/test_install.py::test_package_init_does_not_eagerly_import_adapter` regression-tests this.
