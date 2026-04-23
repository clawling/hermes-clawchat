# ClawChat Plugin Installed

Hermes `plugins install` only clones the Git plugin. Run the bundled installer once to patch/register the ClawChat gateway:

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}" HERMES_DIR="${HERMES_DIR:-$HOME/.hermes/hermes-agent}" node "$HERMES_HOME/plugins/clawchat/bin/hermes-clawchat.js" install
```

For Docker deployments:

```bash
docker exec hermes sh -lc 'HERMES_HOME=/opt/data HERMES_DIR=/opt/hermes node /opt/data/plugins/clawchat/bin/hermes-clawchat.js install'
```

Then restart Hermes:

```bash
hermes gateway restart
```

For Docker:

```bash
docker restart hermes
```

After restart, activate ClawChat by telling Hermes:

```text
ClawChat 的激活码是 R4E1IW
```

The installer registers the ClawChat skill and gateway adapter.
