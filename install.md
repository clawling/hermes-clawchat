# Install `hermes-clawchat` Plugin

A guide for installing the ClawChat plugin into a Hermes Agent environment.

## 1. Verify the Hermes environment

Before installing, add the Hermes venv to your `PATH` if it's present at the default location (its existence indicates a Hermes environment):

```bash
if [ -d /opt/hermes/.venv/bin ]; then
    echo "hermes exist"
fi
```

Then confirm that the `hermes` CLI is available on your `PATH`:

```bash
hermes --version
```

- If the command prints a version, you're ready to install.
- If you see `command not found`, install/activate Hermes Agent first (e.g. `source` the Hermes venv or run `which hermes` to locate it), then re-run the check.

Optional sanity checks:

```bash
hermes plugins list        # confirm the plugin subcommand works
echo "$HERMES_HOME"        # defaults to ~/.hermes if unset
```

## 2. Remove any existing installation

If `hermes-clawchat` is already installed, uninstall it first to avoid conflicts with the auto-install patches:

```bash
hermes plugins list | grep hermes-clawchat   # check whether it's installed
hermes plugins uninstall hermes-clawchat     # only if the previous command found it
```

If the plugin is not listed, skip this step.

## 3. Install the plugin

Once `hermes` is available, install from the registry:

```bash
hermes plugins install clawling/hermes-clawchat
```

This will download the plugin, register it with Hermes, and trigger the plugin's auto-install step, which patches the local hermes-agent source to register the `CLAWCHAT` platform.

## 4. Verify installation

```bash
hermes plugins list
```

You should see `hermes-clawchat` listed.

## 5. Apply patches and activate ClawChat

`hermes plugins install` only downloads the plugin — it does **not** auto-apply the hermes-agent patches and does **not** put the `clawchat_gateway` package on the Python import path. Run the two commands below in a single terminal block so both steps share the resolved `PYTHONPATH`. **Do not** start another `hermes chat` session for this step. The activation code is one-time-use and is consumed on first call, so do not retry on success and do not loop.

Use tool:'terminal' to execute exactly:

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_AGENT_DIR="${HERMES_DIR:-${HERMES_AGENT_DIR:-}}"
if [ -z "$HERMES_AGENT_DIR" ]; then
  if [ -d /opt/hermes/gateway ]; then HERMES_AGENT_DIR=/opt/hermes
  else HERMES_AGENT_DIR="$HERMES_HOME/hermes-agent"; fi
fi

PY=""
if [ -x "$HERMES_AGENT_DIR/.venv/bin/python" ]; then
  PY="$HERMES_AGENT_DIR/.venv/bin/python"
elif [ -x /opt/hermes/.venv/bin/python ]; then
  PY="/opt/hermes/.venv/bin/python"
elif [ -x "$HOME/.hermes/hermes-agent/.venv/bin/python" ]; then
  PY="$HOME/.hermes/hermes-agent/.venv/bin/python"
else
  PY="python3"
fi

export PYTHONPATH="$HERMES_HOME/plugins/clawchat/src:${PYTHONPATH:-}"

# Replace CLAWCHAT_CODE_GOES_HERE with the actual activation code the user gave
# you, passed as a positional argument to activate (no stdin redirection, no echo
# pipe). The code is one-time-use and will be consumed on the first call.
CLAWCHAT_CODE="CLAWCHAT_CODE_GOES_HERE"

# 5a. Apply hermes-agent patches (idempotent; required so Platform.CLAWCHAT exists before restart)
"$PY" -m clawchat_gateway.install --hermes-dir "$HERMES_AGENT_DIR"

# 5b. Activate ClawChat (one-time code; do not retry)
"$PY" -m clawchat_gateway.activate "$CLAWCHAT_CODE"
```

Step 5a prints a JSON summary of applied patches. Step 5b prints a JSON envelope with `user_id`, `base_url`, and `websocket_url` and exits with code `0` on success. Treat any non-zero exit as failure and report the stderr verbatim — do not retry the activation command, the code has already been consumed.

## 6. Final Step: Dispatch a Detached Gateway Restart

Run this single line and **stop**. The terminal-tool inside `hermes chat` enforces a 60-second wall-clock cap on foreground commands, and `hermes gateway restart` routinely needs longer than that. So we dispatch it detached and let it finish in its own session — there is nothing to wait for inside the install session.

Use tool:'terminal' to execute exactly once:

```bash
nohup hermes gateway restart </dev/null >/tmp/clawchat-restart.log 2>&1 &
```

The shell returns immediately while the gateway boots in the background. **Do not** run `hermes gateway restart` again in the foreground, **do not** add a follow-up `echo`, and **do not** retry. Reply to the user that ClawChat activation is complete and the gateway is restarting in the background; activation will become live within a few seconds.

