# Install `hermes-clawchat` Plugin

A short, deterministic guide for installing the ClawChat plugin into a Hermes Agent environment. Follow the steps in order. Each step is one tool:'terminal' call — do not split, do not improvise, do not run additional `hermes` commands beyond what is listed here.

## 1. Verify the Hermes environment

```bash
if [ -d /opt/hermes/.venv/bin ]; then
    echo "hermes exist"
fi
hermes --version
```

If `hermes` is not on the path, source the Hermes venv first.

## 2. Remove any existing installation

If `hermes-clawchat` is already installed, uninstall it first:

```bash
hermes plugins list | grep hermes-clawchat
hermes plugins uninstall hermes-clawchat   # only if listed
```

## 3. Install and enable the plugin

```bash
hermes plugins install clawling/hermes-clawchat
hermes plugins enable clawchat
```

This registers the `clawchat_activate` tool and copies the plugin source into `$HERMES_HOME/plugins/clawchat/`.

## 4. Apply hermes-agent patches — one terminal call

Run the block below in **one** tool:'terminal' invocation. This applies the idempotent anchor patches so hermes-agent learns about the `CLAWCHAT` platform; it does **not** activate credentials.

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

"$PY" -m clawchat_gateway.install --hermes-dir "$HERMES_AGENT_DIR"

echo "clawchat: patches applied"
```

## 5. Activate ClawChat — call the `clawchat_activate` tool

Now invoke the **`clawchat_activate` tool** (registered by step 3) with the activation code the user provided in their original message. Pass `code` verbatim — the code is one-time-use; if it fails, surface the error and ask for a fresh code instead of retrying.

Calling the tool (not `python -m clawchat_gateway.activate`) is what schedules the gateway restart: the tool handler saves credentials to `$HERMES_HOME/config.yaml` and then dispatches a detached `hermes gateway restart` after a 2-second delay, so the response returns to the user before the gateway is torn down. The CLI module does not do this — it only writes credentials.

**Do not** run `hermes gateway restart` from inside this chat session — it does not return within the chat tool's 60-second cap and the tool handler has already scheduled the restart in the background.

**Do not** poll `hermes gateway status`, **do not** invoke `clarify`, and **do not** ask the user to confirm anything.

Reply once: "ClawChat is activated and the gateway is restarting in the background; it will be live in a few seconds." That is your final message — stop calling tools.
