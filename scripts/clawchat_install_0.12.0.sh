#!/usr/bin/env bash
# Install hermes-clawchat into a Hermes Agent v0.12.0+ host.
#
# This script is published to Cloudflare R2 by `scripts/package_internal.sh`.
# End-users invoke it as:
#
#     curl -fsSL https://dddddddddddddtest.clawling.chat/plugins/clawchat_install_0.12.0.sh | bash
#
# Steps:
#   1. Verify `hermes` is on PATH (sourcing /opt/hermes/.venv/bin/activate if needed).
#   2. Uninstall any prior `clawchat` plugin so the reinstall is clean.
#   3. Download the matching tarball from R2.
#   4. Extract into $HERMES_HOME/plugins/clawchat/.
#   5. Run `hermes plugins enable clawchat` (the host's built-in mechanism that
#      writes plugins.enabled to the Hermes config).
#   6. Dispatch a detached `hermes gateway restart` so the platform registers.
#
# After this returns, log in with:
#   cd $HERMES_HOME/plugins/clawchat
#   /opt/hermes/.venv/bin/python -m clawchat_gateway.activate <CODE>
#
# Override defaults via env:
#   HERMES_HOME          - default: $HOME/.hermes
#   PLUGIN_VERSION       - default: pinned at packaging time (see below)
#   PLUGIN_BASE_URL      - default: https://dddddddddddddtest.clawling.chat

set -euo pipefail

# `package_internal.sh` rewrites the placeholder below at upload time so the
# published installer points at the tar that was packaged in the same run.
# The `${PLUGIN_VERSION:-…}` form is preserved so end-users can override the
# pinned version via env (`PLUGIN_VERSION=0.2.0 bash …`). The repo copy keeps
# `PLUGIN_VERSION_PLACEHOLDER` so contributors don't see version churn.
PLUGIN_VERSION="${PLUGIN_VERSION:-PLUGIN_VERSION_PLACEHOLDER}"
PLUGIN_BASE_URL="${PLUGIN_BASE_URL:-https://dddddddddddddtest.clawling.chat}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_NAME="clawchat"
TARBALL="hermes-clawchat-${PLUGIN_VERSION}.tar.gz"
TAR_URL="${PLUGIN_BASE_URL}/plugins/${TARBALL}"

log()  { echo "==> $*" >&2; }
fail() { echo "==> ERROR: $*" >&2; exit 1; }

WORK_DIR=""
cleanup() { [[ -n "${WORK_DIR}" && -d "${WORK_DIR}" ]] && rm -rf "${WORK_DIR}"; }
trap cleanup EXIT

# --- 1. Verify hermes is on PATH --------------------------------------------

if ! command -v hermes >/dev/null 2>&1; then
  if [[ -f /opt/hermes/.venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source /opt/hermes/.venv/bin/activate
  fi
fi

command -v hermes >/dev/null 2>&1 \
  || fail "hermes CLI not found on PATH; activate the Hermes venv first"

HERMES_VERSION="$(hermes --version 2>/dev/null || true)"
log "hermes detected: ${HERMES_VERSION:-<unknown>}"
log "HERMES_HOME=${HERMES_HOME}"
log "Installing hermes-clawchat ${PLUGIN_VERSION} from ${TAR_URL}"

# --- 2. Remove any prior installation ---------------------------------------

if hermes plugins list 2>/dev/null | grep -q "^${PLUGIN_NAME}\b\|[[:space:]]${PLUGIN_NAME}[[:space:]]"; then
  log "Removing existing '${PLUGIN_NAME}' plugin"
  hermes plugins uninstall "${PLUGIN_NAME}" || true
fi

# Belt-and-braces: even if `hermes plugins uninstall` failed or the directory
# was placed there manually, scrub the on-disk dir so the extract is clean.
PLUGIN_DIR="${HERMES_HOME}/plugins/${PLUGIN_NAME}"
if [[ -e "${PLUGIN_DIR}" ]]; then
  log "Removing stale ${PLUGIN_DIR}"
  rm -rf "${PLUGIN_DIR}"
fi

# --- 3. Download tarball ----------------------------------------------------

WORK_DIR="$(mktemp -d -t hermes-clawchat.XXXXXX)"
TAR_PATH="${WORK_DIR}/${TARBALL}"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL --retry 3 --retry-delay 2 -o "${TAR_PATH}" "${TAR_URL}" \
    || fail "download failed: ${TAR_URL}"
elif command -v wget >/dev/null 2>&1; then
  wget -q -O "${TAR_PATH}" "${TAR_URL}" \
    || fail "download failed: ${TAR_URL}"
else
  fail "neither curl nor wget is available"
fi

[[ -s "${TAR_PATH}" ]] || fail "downloaded tarball is empty: ${TAR_PATH}"
log "Downloaded $(wc -c < "${TAR_PATH}" | tr -d ' ') bytes to ${TAR_PATH}"

# --- 4. Extract into $HERMES_HOME/plugins/ -----------------------------------

mkdir -p "${HERMES_HOME}/plugins"
# The tar was built with `--prefix=clawchat/`, so this lands files at
# $HERMES_HOME/plugins/clawchat/...
tar -xzf "${TAR_PATH}" -C "${HERMES_HOME}/plugins" \
  || fail "tar extract failed"

[[ -f "${PLUGIN_DIR}/plugin.yaml" ]] \
  || fail "extracted tree missing plugin.yaml at ${PLUGIN_DIR}"

log "Extracted plugin into ${PLUGIN_DIR}"

# --- 5. Enable via the host's built-in mechanism ----------------------------

log "Enabling plugin via 'hermes plugins enable ${PLUGIN_NAME}'"
hermes plugins enable "${PLUGIN_NAME}"

# --- 6. Dispatch detached gateway restart -----------------------------------
#
# The restart can take longer than 60s, so detach it from the current shell
# the same way `clawchat_gateway.activate` does. The script returns
# immediately even though the gateway is still coming up.

log "Dispatching detached 'hermes gateway restart' (will land in ~2s)"
nohup sh -lc 'sleep 2; hermes gateway restart' >/dev/null 2>&1 &
disown || true

cat <<EOF

==> Install complete.

    Plugin:        ${PLUGIN_NAME} ${PLUGIN_VERSION}
    Plugin dir:    ${PLUGIN_DIR}
    Gateway:       restart dispatched (background)

    Next step — activate against your ClawChat account. Replace
    CLAWCHAT_CODE_GOES_HERE with a fresh activation code:

        cd ${PLUGIN_DIR}
        /opt/hermes/.venv/bin/python -m clawchat_gateway.activate CLAWCHAT_CODE_GOES_HERE

    The activate CLI writes CLAWCHAT_TOKEN/CLAWCHAT_REFRESH_TOKEN to
    ${HERMES_HOME}/.env, writes platform config to ${HERMES_HOME}/config.yaml,
    and triggers another detached gateway restart.
EOF
