SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "missing env file: $ENV_FILE (expected JWT=...)" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

if [ -z "${JWT:-}" ]; then
    echo "JWT not set in $ENV_FILE" >&2
    exit 1
fi

case "$JWT" in
    Bearer\ *) AUTH_HEADER="$JWT" ;;
    *)         AUTH_HEADER="Bearer $JWT" ;;
esac

RESPONSE=$(curl -sS --location --request POST 'https://app.clawling.com/v1/agents/connect-codes' \
    --header 'x-device-id: apifox' \
    --header "Authorization: $AUTH_HEADER")

echo "connect-codes response: $RESPONSE"

CODE=$(echo "$RESPONSE" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('data', {}).get('code') or d.get('code', ''))")

if [ -z "$CODE" ]; then
    echo "failed to obtain connect code" >&2
    exit 1
fi

echo "connect code: $CODE"

if [ ! -d ./.e2e/tmp/hermes_data_base ]; then
    cat >&2 <<'EOF'
missing baseline Hermes data dir: ./.e2e/tmp/hermes_data_base

Each test run is freshly seeded by copying ./.e2e/tmp/hermes_data_base ->
./.e2e/tmp/hermes_data, so the baseline must exist first. Bootstrap it
once by running Hermes interactively against an empty dir, completing
the first-run setup (model / API keys), then exiting:

    mkdir -p ./.e2e/tmp/hermes_data_base
    docker run -it --rm -v ./.e2e/tmp/hermes_data_base:/opt/data \
        nousresearch/hermes-agent chat

After it exits, ./.e2e/tmp/hermes_data_base will hold the initialized
config Hermes needs and you can re-run this script.
EOF
    exit 1
fi

rm -rf ./.e2e/tmp/hermes_data
cp -r ./.e2e/tmp/hermes_data_base ./.e2e/tmp/hermes_data
rm -rf ./.e2e/tmp/hermes_data/plugins/clawchat
rm -rf ./.e2e/tmp/hermes_data/plugins/hermes-clawchat

INSTALL_PROMPT=$(cat <<EOF
Here is the connect <CODE>: $CODE.

Install and configure ClawChat for Hermes Agent by following the npm CLI
installation path from:
https://plugin.clawling.chat/clawchat/install.md

Do not use hermes plugins install, do not install from /tmp/hermes-clawchat,
and do not run the legacy clawchat_gateway.install fallback.

Run the commands below in order. Each fenced block is one tool:'terminal' call.
If any command exits non-zero, report the stderr or JSON response verbatim and
stop. The connect code is one-time-use; do not retry activation with the same
code.

1. Verify Hermes:

\`\`\`bash
if ! command -v hermes >/dev/null 2>&1; then
  if [ -d /opt/hermes/.venv/bin ]; then
    . /opt/hermes/.venv/bin/activate
  elif [ -d "\$HOME/.hermes/hermes-agent/.venv/bin" ]; then
    . "\$HOME/.hermes/hermes-agent/.venv/bin/activate"
  fi
fi

hermes --version
\`\`\`

2. Install or refresh the ClawChat CLI with npm:

\`\`\`bash
npm install -g @newbase-clawchat/clawchat-cli@latest
clawchat --help
\`\`\`

3. Install the Hermes plugin and skill through the CLI:

\`\`\`bash
clawchat install --target hermes
\`\`\`

4. Activate with the provided connect code:

\`\`\`bash
clawchat call activate --target hermes --input '{"code":"$CODE"}'
\`\`\`

5. Restart the Hermes gateway once after activation:

\`\`\`bash
hermes gateway restart
\`\`\`

6. Verify target auth:

\`\`\`bash
clawchat call get_account_profile --target hermes --input '{}'
\`\`\`

Reply once, and only after the profile check succeeds:
"ClawChat is activated and verified for Hermes."
EOF
)

docker run -it --rm \
    -v ./.e2e/tmp/hermes_data:/opt/data \
    nousresearch/hermes-agent chat -q "$INSTALL_PROMPT"
#docker run -it --rm  -v ./.e2e/tmp/hermes_data:/opt/data nousresearch/hermes-agent gateway run
#docker run -it -v ./.e2e/tmp/hermes_data:/opt/data nousresearch/hermes-agent gateway run
