# Install `hermes-clawchat` Plugin (joe/test branch)

A short, deterministic guide for installing the ClawChat plugin from the `joe/test` branch. Follow the steps in order. Each step is one tool:'terminal' call — do not split, do not improvise, do not run additional `hermes` commands beyond what is listed here.

## 1. Verify the Hermes environment

```bash
if [ -d /opt/hermes/.venv/bin ]; then
    echo "hermes exist"
fi
hermes --version
```

If `hermes` is not on the path, source the Hermes venv first.

## 2. Remove any existing installation

```bash
hermes plugins list | grep hermes-clawchat
hermes plugins uninstall hermes-clawchat   # only if listed
```

## 3. Install and enable the plugin from joe/test

`hermes plugins install` shallow-clones the default branch, so for a feature branch we clone the branch ourselves and hand Hermes a local path:

```bash
rm -rf /tmp/hermes-clawchat
git clone --depth 1 --branch joe/test https://github.com/clawling/hermes-clawchat.git /tmp/hermes-clawchat
hermes plugins install file:///tmp/hermes-clawchat
hermes plugins enable clawchat
```

This registers the `clawchat_activate` tool and copies the plugin source into `$HERMES_HOME/plugins/clawchat/`.

## 4. Bootstrap, activate, and dispatch the restart — one terminal call, then stop

Run the block below in **one** tool:'terminal' invocation. Replace `CLAWCHAT_CODE_GOES_HERE` with the activation code the user provided in their original message — pass it as a positional argument to `clawchat_gateway.activate` (no stdin pipe, no `echo | …`). The code is one-time-use; if the command fails, surface the stderr verbatim and ask for a fresh code instead of retrying.

```bash
set -e

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_AGENT_DIR="${HERMES_DIR:-${HERMES_AGENT_DIR:-}}"
if [ -z "$HERMES_AGENT_DIR" ]; then
  if [ -d /opt/hermes/gateway ]; then HERMES_AGENT_DIR=/opt/hermes
  else HERMES_AGENT_DIR="$HERMES_HOME/hermes-agent"; fi
fi

if   [ -x "$HERMES_AGENT_DIR/.venv/bin/python" ];        then PY="$HERMES_AGENT_DIR/.venv/bin/python"
elif [ -x /opt/hermes/.venv/bin/python ];                then PY="/opt/hermes/.venv/bin/python"
elif [ -x "$HOME/.hermes/hermes-agent/.venv/bin/python" ]; then PY="$HOME/.hermes/hermes-agent/.venv/bin/python"
else PY="python3"; fi

export PYTHONPATH="$HERMES_HOME/plugins/clawchat/src:${PYTHONPATH:-}"

CLAWCHAT_CODE="CLAWCHAT_CODE_GOES_HERE"

# Apply hermes-agent patches (idempotent; no-op if already applied)
"$PY" -m clawchat_gateway.install --hermes-dir "$HERMES_AGENT_DIR"

# Activate ClawChat. One-time code — do not retry.
"$PY" -m clawchat_gateway.activate "$CLAWCHAT_CODE"

# Dispatch the gateway restart detached. Returns immediately; the gateway
# finishes restarting in its own session a few seconds later.
nohup hermes gateway restart </dev/null >/tmp/clawchat-restart.log 2>&1 &
```

When this block exits, the install is complete. The `&` on the last line will surface as `[error]` in the chat-tool UI — that is just how the chat-tool labels backgrounded commands; the restart **is** running in its own session. **Do not** run `hermes gateway restart` again in the foreground (it will just hit the chat-tool's 60-second timeout and add nothing), **do not** poll `hermes gateway status`, **do not** invoke `clarify`, and **do not** ask the user to confirm anything.

Reply once: "ClawChat is activated and the gateway is restarting in the background; it will be live in a few seconds." That is your final message — stop calling tools.
