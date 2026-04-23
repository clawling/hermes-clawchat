#!/usr/bin/env sh
set -eu

VERSION="${CLAWCHAT_GATEWAY_VERSION:-0.1.0}"
PACKAGE_NAME="clawchat-gateway-installer-$VERSION.tar.gz"
INSTALL_TMP="${CLAWCHAT_GATEWAY_TMP:-/tmp}"
DEFAULT_BASE_URL="https://hermes.nbv587cc99.win"

if [ -n "${CLAWCHAT_GATEWAY_PACKAGE_URL:-}" ]; then
  PACKAGE_URL="$CLAWCHAT_GATEWAY_PACKAGE_URL"
elif [ -n "${CLAWCHAT_GATEWAY_BASE_URL:-}" ]; then
  PACKAGE_URL="${CLAWCHAT_GATEWAY_BASE_URL%/}/$PACKAGE_NAME"
else
  PACKAGE_URL="$DEFAULT_BASE_URL/$PACKAGE_NAME"
fi

ARCHIVE="$INSTALL_TMP/$PACKAGE_NAME"
EXTRACT_DIR="$INSTALL_TMP/clawchat-gateway-installer-$VERSION"

download() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$PACKAGE_URL" -o "$ARCHIVE"
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO "$ARCHIVE" "$PACKAGE_URL"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$PACKAGE_URL" "$ARCHIVE" <<'PY'
import sys
from urllib.request import urlopen

url, path = sys.argv[1], sys.argv[2]
with urlopen(url) as response, open(path, "wb") as handle:
    handle.write(response.read())
PY
    return
  fi
  if command -v python >/dev/null 2>&1; then
    python - "$PACKAGE_URL" "$ARCHIVE" <<'PY'
import sys
try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

url, path = sys.argv[1], sys.argv[2]
response = urlopen(url)
try:
    data = response.read()
finally:
    response.close()
with open(path, "wb") as handle:
    handle.write(data)
PY
    return
  fi
  echo "error: curl, wget, python3, or python is required to download $PACKAGE_URL" >&2
  exit 2
}

echo "Downloading ClawChat gateway package: $PACKAGE_URL"
download

rm -rf "$EXTRACT_DIR"
tar -xzf "$ARCHIVE" -C "$INSTALL_TMP"

"$EXTRACT_DIR/scripts/install-package.sh"
