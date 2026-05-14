# Runtime Defaults

Modern Hermes builds load ClawChat through the plugin platform registry. This
module contains the small startup defaults that are still useful after the
platform is registered.

## `clawchat_gateway/runtime_defaults.py`

| Function | Signature | Purpose |
|---|---|---|
| `_hermes_home` | `() -> Path` | `$HERMES_HOME` or `~/.hermes`. |
| `_env_file` | `() -> Path` | `$HERMES_HOME/.env`. |
| `configure_clawchat_allow_all` | `() -> bool` | Ensures `CLAWCHAT_ALLOW_ALL_USERS=true` is present in `$HERMES_HOME/.env`. Returns `True` if changed. |
| `configure_clawchat_streaming` | `() -> bool` | Writes/updates `config.yaml`: `platforms.clawchat.extra.reply_mode=stream`, hides raw think/tool output, enables edit streaming defaults, and disables ClawChat reasoning/progress display noise. Returns `True` if changed. |

`register(ctx)` calls both helpers after `ctx.register_platform(...)` succeeds.
