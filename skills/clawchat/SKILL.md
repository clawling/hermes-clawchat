---
name: clawchat
description: Activate and operate the ClawChat Hermes gateway integration. Use when the user asks to configure ClawChat, says they have a ClawChat activation code, or asks whether ClawChat is connected.
version: 1.0.0
metadata:
  hermes:
    tags: [clawchat, gateway, activation, messaging]
---

# ClawChat Gateway

Use this skill when the user wants to activate or configure ClawChat for Hermes.

## Hermes Python

Always use the Hermes Python environment, not the system Python, when running ClawChat commands:

```bash
PY="${HERMES_PYTHON:-}"
if [ -z "$PY" ] && [ -n "${HERMES_DIR:-}" ] && [ -x "$HERMES_DIR/.venv/bin/python" ]; then
  PY="$HERMES_DIR/.venv/bin/python"
fi
if [ -z "$PY" ] && [ -x "$HOME/.hermes/hermes-agent/.venv/bin/python" ]; then
  PY="$HOME/.hermes/hermes-agent/.venv/bin/python"
fi
if [ -z "$PY" ] && [ -x /opt/hermes/.venv/bin/python ]; then
  PY="/opt/hermes/.venv/bin/python"
fi
if [ -z "$PY" ]; then
  PY="python3"
fi
```

## Activation Flow

If the user asks to activate ClawChat but has not provided a code, ask for the ClawChat activation code.

If the user provides a code, extract it verbatim. Examples:

- `clawchat 的激活码是 R4E1IW` -> `R4E1IW`
- `ClawChat激活码: R4E1IW` -> `R4E1IW`
- `激活 clawchat R4E1IW` -> `R4E1IW`

Then run with the Hermes Python environment, not the system Python:

```bash
"$PY" -m clawchat_gateway.activate CODE
```

If Hermes uses a non-default home or agent directory, preserve the current environment, especially `HERMES_HOME`.

The activation command calls `/v1/agents/connect`, stores `token`, `refresh_token`, `user_id`, `base_url`, and `websocket_url` in `config.yaml`, and configures ClawChat stream output.

After activation succeeds, restart Hermes automatically before replying to the user. Prefer these commands in order:

```bash
if [ -n "${HERMES_DIR:-}" ] && [ -x "$HERMES_DIR/.venv/bin/hermes" ]; then
  "$HERMES_DIR/.venv/bin/hermes" gateway restart
elif [ -x "$HOME/.hermes/hermes-agent/.venv/bin/hermes" ]; then
  "$HOME/.hermes/hermes-agent/.venv/bin/hermes" gateway restart
elif [ -x /opt/hermes/.venv/bin/hermes ]; then
  HERMES_HOME="${HERMES_HOME:-/opt/data}" /opt/hermes/.venv/bin/hermes gateway restart
elif command -v hermes >/dev/null 2>&1; then
  hermes gateway restart
else
  echo "warning: hermes restart command not found"
fi
```

If the restart command succeeds, tell the user ClawChat activation is complete and Hermes has been restarted. If restart fails, report that activation succeeded but restart must still be done manually.

## Update Nickname

Use this flow when the user asks to change the ClawChat bot name, assistant name, display name, or nickname. Trigger phrases include:

- `你叫 小助手`
- `把 ClawChat 昵称改成 小助手`
- `change your name to Hermes Bot`
- `update nickname to Hermes Bot`

Extract the nickname exactly as requested, then run:

```bash
"$PY" -m clawchat_gateway.profile nickname "NEW_NICKNAME"
```

If the command succeeds, tell the user the nickname was updated. If it fails because ClawChat is not activated, ask the user for the ClawChat activation code first.

## Update Avatar

Use this flow when the user asks to change the ClawChat avatar, upload an avatar, or use an attached image as the avatar.

Avatar updates require a local absolute file path. Do not pass an HTTP URL to the profile command. If the user sent an image through ClawChat, use the downloaded local media path exposed to the agent by the ClawChat runtime. If no local path is available, ask the user to provide an absolute local file path.

Always upload first, then update the profile with the uploaded URL. Do not call the profile update API directly with a local path.

Run:

```bash
"$PY" -m clawchat_gateway.profile avatar "/absolute/path/to/avatar.png"
```

The command enforces this sequence internally: upload the local file through `/v1/files/upload-url`, then update the ClawChat profile with the returned avatar URL.

## Defaults

Default API endpoint:

```text
http://company.newbaselab.com:10086
```

Default WebSocket endpoint:

```text
ws://company.newbaselab.com:10086/ws
```

Do not call `connect-codes`; activation uses `/v1/agents/connect`.

## Useful Checks

Show current ClawChat config:

```bash
python - <<'PY'
import yaml
from pathlib import Path
import os
p = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "config.yaml"
c = yaml.safe_load(p.read_text()) or {}
print(yaml.safe_dump(c.get("platforms", {}).get("clawchat", {}), sort_keys=False))
PY
```

Check gateway logs for connection state:

```bash
tail -n 120 ~/.hermes/logs/agent.log | grep -i clawchat
```

For Docker deployments, use the container log command appropriate to the environment, for example:

```bash
docker logs --since 10m hermes | grep -i clawchat
```
