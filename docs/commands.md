# Slash Commands — `clawchat_gateway/commands.py`

Registers and handles the Hermes in-session `/clawchat-activate ...` command through `ctx.register_command(...)`.

## `/clawchat-activate`

```text
usage: /clawchat-activate CODE [--base-url URL] [--no-restart]
```

- `CODE` - required ClawChat activation code.
- `--base-url` - optional ClawChat HTTP API base URL; defaults to `DEFAULT_BASE_URL`.
- `--no-restart` - persist activation but skip the detached Hermes gateway restart.

The handler parses raw slash-command arguments with `shlex.split`, returns a short usage string for malformed input, then calls:

```python
activate_and_maybe_restart(
    args.code,
    base_url=args.base_url,
    restart=not args.no_restart,
)
```

On success, it returns concise status lines:

```text
clawchat: activation complete for <user_id>
clawchat: Hermes restart scheduled in 2s
```

The restart line is omitted when `--no-restart` is used.
