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

On Hermes v0.12.0 and newer this loads ClawChat as a pluggable gateway platform. The plugin calls `ctx.register_platform(...)` at startup, so the ClawChat adapter is recognized by the gateway without patching Hermes source files. This also registers the seven `clawchat_*` tools and copies the plugin source into `$HERMES_HOME/plugins/clawchat/`.

## 4. Activate and dispatch the restart — one terminal call, then stop

Run the block below in **one** tool:'terminal' invocation. Replace `CLAWCHAT_CODE_GOES_HERE` with the activation code the user provided in their original message — pass it as a positional argument to `clawchat_gateway.activate` (no stdin pipe, no `echo | …`). The code is one-time-use; if the command fails, surface the stderr verbatim and ask for a fresh code instead of retrying.

```bash
set -e

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_DIR="$HERMES_HOME/plugins/clawchat"

if   [ -x /opt/hermes/.venv/bin/python ];                then PY="/opt/hermes/.venv/bin/python"
elif [ -x "$HOME/.hermes/hermes-agent/.venv/bin/python" ]; then PY="$HOME/.hermes/hermes-agent/.venv/bin/python"
else PY="python3"; fi

export HERMES_HOME
export PYTHONPATH="$PLUGIN_DIR/src:$PLUGIN_DIR:${PYTHONPATH:-}"

CLAWCHAT_CODE="CLAWCHAT_CODE_GOES_HERE"

# Activate ClawChat. The CLI writes CLAWCHAT_TOKEN and
# CLAWCHAT_REFRESH_TOKEN to $HERMES_HOME/.env, writes non-secret
# ClawChat platform config to config.yaml, and dispatches a detached
# `hermes gateway restart` so the gateway picks up the new credentials.
# One-time code — do not retry on failure.
"$PY" -m clawchat_gateway.activate "$CLAWCHAT_CODE"

echo "clawchat: activation + restart dispatched"
```

When this block exits cleanly, the install is done. On Hermes v0.12.0+, the enabled plugin registers the ClawChat adapter through Hermes `ctx.register_platform(...)`; do **not** run `python -m clawchat_gateway.install --hermes-dir ...` on Hermes versions that support plugin platform registration. That patch installer is only a legacy fallback for older Hermes builds without pluggable gateway platforms.

The `clawchat_gateway.activate` CLI dispatches a detached `sh -lc 'sleep 2; hermes gateway restart'` after writing `CLAWCHAT_TOKEN` and `CLAWCHAT_REFRESH_TOKEN`, so the gateway restart happens in the background without any further action — you do **not** need to ask the user (or anyone) to run `hermes gateway restart` manually.

**Do not** run `hermes gateway restart` yourself from inside this chat session — it does not return within the chat tool's 60-second cap, and the activate CLI has already scheduled it. **Do not** poll `hermes gateway status`, **do not** invoke `clarify`, and **do not** ask the user to confirm anything.

Reply once: "ClawChat is activated and the gateway is restarting in the background; it will be live in a few seconds." That is your final message — stop calling tools.
