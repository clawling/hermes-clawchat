# Hermes ClawChat

Install the ClawChat gateway integration into a Hermes Agent instance:

```bash
npx -y @newbase-clawchat/hermes-clawchat@latest install
```

For Docker/container deployments, set the Hermes paths explicitly:

```bash
HERMES_HOME=/opt/data HERMES_DIR=/opt/hermes npx -y @newbase-clawchat/hermes-clawchat@latest install
```

Defaults:

- `HERMES_HOME`: `~/.hermes`
- `HERMES_DIR`: `~/.hermes/hermes-agent`
- install source: `$HERMES_HOME/plugins/clawchat-gateway-src`

Restart Hermes after installation so the gateway and ClawChat skill are loaded.

## Install With Hermes Plugins

Hermes plugins are installed from Git repositories:

```bash
hermes plugins install newbase-clawchat/hermes-clawchat
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}" HERMES_DIR="${HERMES_DIR:-$HOME/.hermes/hermes-agent}" node "$HERMES_HOME/plugins/clawchat/bin/hermes-clawchat.js" install
hermes gateway restart
```

For Docker:

```bash
docker exec hermes sh -lc 'HERMES_HOME=/opt/data /opt/hermes/.venv/bin/hermes plugins install newbase-clawchat/hermes-clawchat --force'
docker exec hermes sh -lc 'HERMES_HOME=/opt/data HERMES_DIR=/opt/hermes node /opt/data/plugins/clawchat/bin/hermes-clawchat.js install'
docker restart hermes
```
