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

1. `_register_python_path(_plugin_dir() / "src")`
2. `_register_tools(ctx)`
3. If `skills/clawchat/SKILL.md` exists, `ctx.register_skill("clawchat", skill, description=...)`.
4. Try `_install_gateway()`; on `Exception`, log a warning and continue.

## `src/clawchat_gateway/__init__.py`

Public package surface:

```python
from clawchat_gateway.adapter import ClawChatAdapter, check_clawchat_requirements
__version__ = "0.1.0"
__all__ = ["__version__", "ClawChatAdapter", "check_clawchat_requirements"]
```

Importing the package forces `adapter.py` to load, which in turn imports `gateway.platforms.base` — make sure hermes-agent stubs are installed (`tests/fake_hermes.py`) if you import this from tests.
