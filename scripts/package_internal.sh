#!/usr/bin/env bash
# Package this plugin into a tar.gz of HEAD and upload it (along with the
# matching install script) to Cloudflare R2 so end-users can install via the
# `clawchat_install_0.12.0.sh` one-liner.
#
# Usage:
#   scripts/package_internal.sh                # build + upload
#   scripts/package_internal.sh --no-upload    # build only
#   scripts/package_internal.sh --version X.Y  # override version from plugin.yaml
#
# Requirements: git, tar, sed, awscli (`brew install awscli`), and a populated
# scripts/.env.r2 with R2 credentials (see scripts/.env.r2.example).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist"
R2_ENV_FILE="${SCRIPT_DIR}/.env.r2"

NO_UPLOAD="false"
VERSION_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-upload) NO_UPLOAD="true"; shift ;;
    --version)   VERSION_OVERRIDE="${2:?--version requires a value}"; shift 2 ;;
    -h|--help)
      sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

# --- Resolve plugin version --------------------------------------------------

if [[ -n "${VERSION_OVERRIDE}" ]]; then
  VERSION="${VERSION_OVERRIDE}"
else
  VERSION="$(awk -F': *' '/^version:/ {gsub(/["'"'"']/, "", $2); print $2; exit}' "${REPO_ROOT}/plugin.yaml")"
fi

if [[ -z "${VERSION}" ]]; then
  echo "==> ERROR: could not determine plugin version from plugin.yaml" >&2
  exit 1
fi

TARBALL="hermes-clawchat-${VERSION}.tar.gz"
TARBALL_PATH="${DIST_DIR}/${TARBALL}"
INSTALL_SCRIPT_SRC="${SCRIPT_DIR}/clawchat_install_0.12.0.sh"
INSTALL_SCRIPT_NAME="clawchat_install_0.12.0.sh"
INSTALL_SCRIPT_STAGED="${DIST_DIR}/${INSTALL_SCRIPT_NAME}"

mkdir -p "${DIST_DIR}"

# --- Build tar via `git archive` --------------------------------------------
#
# `--prefix=clawchat/` so the tar extracts directly into
# `$HERMES_HOME/plugins/clawchat/` without a rename step on the install side.

echo "==> Building ${TARBALL} (git archive HEAD, prefix=clawchat/)" >&2
( cd "${REPO_ROOT}" && git archive --format=tar.gz --prefix=clawchat/ HEAD -o "${TARBALL_PATH}" )

SIZE_BYTES="$(wc -c < "${TARBALL_PATH}" | tr -d ' ')"
SIZE_KB=$(( SIZE_BYTES / 1024 ))
echo "==> Built ${TARBALL_PATH} (${SIZE_KB} KB)" >&2

# --- Stage install script with version pinned -------------------------------

if [[ ! -f "${INSTALL_SCRIPT_SRC}" ]]; then
  echo "==> ERROR: ${INSTALL_SCRIPT_SRC} not found" >&2
  exit 1
fi

# Rewrite the PLUGIN_VERSION_PLACEHOLDER token so the published installer
# points at the tar that was just built. We replace only the default value
# inside `${PLUGIN_VERSION:-…}` so end-users can still override via env.
if ! grep -q 'PLUGIN_VERSION_PLACEHOLDER' "${INSTALL_SCRIPT_SRC}"; then
  echo "==> ERROR: ${INSTALL_SCRIPT_SRC} is missing the PLUGIN_VERSION_PLACEHOLDER token" >&2
  exit 1
fi

sed "s/PLUGIN_VERSION_PLACEHOLDER/${VERSION}/g" \
  "${INSTALL_SCRIPT_SRC}" > "${INSTALL_SCRIPT_STAGED}"
chmod +x "${INSTALL_SCRIPT_STAGED}"

if grep -q 'PLUGIN_VERSION_PLACEHOLDER' "${INSTALL_SCRIPT_STAGED}"; then
  echo "==> ERROR: failed to substitute PLUGIN_VERSION_PLACEHOLDER in staged installer" >&2
  exit 1
fi

echo "==> Staged installer: ${INSTALL_SCRIPT_STAGED} (PLUGIN_VERSION=${VERSION})" >&2

# --- Upload to R2 ------------------------------------------------------------

if [[ "${NO_UPLOAD}" == "true" ]]; then
  echo "==> Skipping R2 upload (--no-upload)" >&2
  echo "==> Local artifacts:" >&2
  echo "    ${TARBALL_PATH}" >&2
  echo "    ${INSTALL_SCRIPT_STAGED}" >&2
  exit 0
fi

if [[ ! -f "${R2_ENV_FILE}" ]]; then
  echo "==> R2 upload FAILED: ${R2_ENV_FILE} not found" >&2
  echo "    Copy scripts/.env.r2.example to scripts/.env.r2 and fill in" >&2
  echo "    credentials, or pass --no-upload to suppress this." >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "==> R2 upload FAILED: aws CLI not found in PATH" >&2
  echo "    Install with: brew install awscli" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "${R2_ENV_FILE}"; set +a

: "${AWS_ACCESS_KEY_ID:?missing in ${R2_ENV_FILE}}"
: "${AWS_SECRET_ACCESS_KEY:?missing in ${R2_ENV_FILE}}"
: "${R2_ENDPOINT:?missing in ${R2_ENV_FILE}}"
: "${R2_BUCKET:?missing in ${R2_ENV_FILE}}"
: "${AWS_DEFAULT_REGION:=auto}"
export AWS_DEFAULT_REGION

TAR_KEY="plugins/${TARBALL}"
SCRIPT_KEY="plugins/${INSTALL_SCRIPT_NAME}"

echo "==> Uploading tar:    s3://${R2_BUCKET}/${TAR_KEY} (${SIZE_KB} KB)" >&2
aws s3 cp \
  "${TARBALL_PATH}" \
  "s3://${R2_BUCKET}/${TAR_KEY}" \
  --endpoint-url "${R2_ENDPOINT}" \
  --content-type application/gzip >&2

echo "==> Uploading script: s3://${R2_BUCKET}/${SCRIPT_KEY}" >&2
aws s3 cp \
  "${INSTALL_SCRIPT_STAGED}" \
  "s3://${R2_BUCKET}/${SCRIPT_KEY}" \
  --endpoint-url "${R2_ENDPOINT}" \
  --content-type text/x-shellscript \
  --cache-control "no-cache" >&2

PUBLIC_BASE="https://dddddddddddddtest.clawling.chat"
echo "==> Done." >&2
echo "    tar:    ${PUBLIC_BASE}/${TAR_KEY}"
echo "    script: ${PUBLIC_BASE}/${SCRIPT_KEY}"
echo
echo "    End-user install one-liner:"
echo "    curl -fsSL ${PUBLIC_BASE}/${SCRIPT_KEY} | bash"
