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

## Tools

Hermes registers seven ClawChat tools:

- `clawchat_activate` — exchange an activation code for ClawChat credentials and persist them into Hermes config.
- `clawchat_get_account_profile` — fetch the configured ClawChat account profile.
- `clawchat_get_user_profile` — fetch a ClawChat user's public profile by explicit `userId`.
- `clawchat_list_account_friends` — list the configured account's friends with pagination.
- `clawchat_update_account_profile` — update nickname, avatar URL, and/or bio.
- `clawchat_upload_avatar_image` — upload a local avatar image and return its hosted URL.
- `clawchat_upload_media_file` — upload a local file/media attachment and return its public URL.

## Quickstart

```bash
# Activate (one-time)
python -m clawchat_gateway.activate <CODE>

# Inspect / update
python -m clawchat_gateway.profile get
python -m clawchat_gateway.profile update --nickname "Bot" --bio "hi"
python -m clawchat_gateway.profile upload-avatar /abs/path/to/image.png
python -m clawchat_gateway.profile upload-media /abs/path/to/file.pdf
python -m clawchat_gateway.profile friends --page 1 --page-size 20
python -m clawchat_gateway.profile get-user <USER_ID>
```

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
