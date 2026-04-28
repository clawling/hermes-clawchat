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

The `hermes plugins install` command always shallow-clones the default branch, so to install from `joe/test` we clone the branch ourselves and hand Hermes a local path:

```bash
rm -rf /tmp/hermes-clawchat
git clone --depth 1 --branch joe/test https://github.com/clawling/hermes-clawchat.git /tmp/hermes-clawchat
hermes plugins install file:///tmp/hermes-clawchat
```

This will download the plugin, register it with Hermes, and trigger the plugin's auto-install step, which patches the local hermes-agent source to register the `CLAWCHAT` platform.

## 4. Verify installation

```bash
hermes plugins list
```

You should see `hermes-clawchat` listed.

## 5. Activate ClawChat with the connect code

Activate by calling the plugin CLI directly with the Hermes Python — **do not** start another `hermes chat` session for this step. The activation code is one-time-use and is consumed on first call, so do not retry on success and do not loop.

Use tool:'terminal' to execute:

```bash
PY=""
if [ -n "${HERMES_DIR:-}" ] && [ -x "$HERMES_DIR/.venv/bin/python" ]; then
  PY="$HERMES_DIR/.venv/bin/python"
elif [ -x "$HOME/.hermes/hermes-agent/.venv/bin/python" ]; then
  PY="$HOME/.hermes/hermes-agent/.venv/bin/python"
elif [ -x /opt/hermes/.venv/bin/python ]; then
  PY="/opt/hermes/.venv/bin/python"
else
  PY="python3"
fi
"$PY" -m clawchat_gateway.activate <CODE>
```

The command prints a JSON envelope with `user_id`, `base_url`, and `websocket_url` and exits with code `0` on success. Treat any non-zero exit as failure and report the stderr verbatim — do not retry the command, the code has already been consumed.

## 6. Last Step Restart Hermes Gateway

After activation succeeds, use tool:'terminal' to execute the following command exactly once:

```bash
hermes gateway restart
```

