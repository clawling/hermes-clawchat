# Install `hermes-clawchat` Plugin

A guide for installing the ClawChat plugin into a Hermes Agent environment.

## 1. Verify the Hermes environment

Before installing, confirm that the `hermes` CLI is available on your `PATH`:

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

You should see `hermes-clawchat` listed. After this, you can activate a ClawChat account via the `clawchat_activate` tool or:

```bash
python -m clawchat_gateway.activate <CODE>
```
