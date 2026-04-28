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

## 2. Remove any existing installation

If `hermes-clawchat` is already installed, uninstall it first to avoid conflicts with the auto-install patches:

```bash
hermes plugins list | grep hermes-clawchat   # check whether it's installed
hermes plugins uninstall hermes-clawchat     # only if the previous command found it
```

If the plugin is not listed, skip this step.

## 3. Install the plugin

Install from the registry; this clones the plugin and runs its `register()` hook, which patches the local hermes-agent source to add the `CLAWCHAT` platform and registers the `clawchat_activate` tool with the running session:

```bash
hermes plugins install clawling/hermes-clawchat
hermes plugins enable clawchat
```

`hermes plugins list` should now show `clawchat`.

## 4. Activate ClawChat — call the registered tool, do not shell out

After step 3, the `clawchat_activate` tool is **already registered with the running Hermes session**. The user's activation code was supplied in their original message (look for `<CODE>: …` or `code is …`); use it verbatim.

**Immediately** invoke the `clawchat_activate` tool with `code = "<the activation code from the user message>"`. Do **not** ask the user to confirm, do **not** call the `clarify` tool, do **not** echo the code back asking for permission — they already gave you the code; the only thing left is to call the tool.

**Do not**:
- start another `hermes chat` session for activation,
- run `python -m clawchat_gateway.activate` from the terminal,
- run `hermes gateway restart` afterwards (foreground or background).

The tool persists the credentials to `~/.hermes/config.yaml` **and** dispatches a detached gateway restart for you (via `_schedule_gateway_restart`, in its own session, immune to the chat terminal-tool's 60-second timeout). Running a second `hermes gateway restart` in the foreground will simply hit that 60-second timeout and add nothing.

The activation code is one-time-use — it is consumed on the first call to `/v1/agents/connect`. **Do not retry on failure**: if the tool returns a non-zero result, surface the error verbatim to the user and ask for a fresh code.

When the tool returns successfully, reply once with a short confirmation that ClawChat is activated and the gateway is restarting in the background; ClawChat will be live within a few seconds.
