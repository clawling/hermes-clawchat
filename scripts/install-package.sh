#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_DIR="${HERMES_DIR:-$HERMES_HOME/hermes-agent}"
PYTHON="${HERMES_PYTHON:-$HERMES_DIR/.venv/bin/python}"
INSTALL_SRC="${CLAWCHAT_GATEWAY_SRC:-$HERMES_HOME/plugins/clawchat-gateway-src}"

if [ ! -x "$PYTHON" ]; then
  echo "error: Hermes Python not found or not executable: $PYTHON" >&2
  echo "set HERMES_DIR=/path/to/hermes or HERMES_PYTHON=/path/to/python" >&2
  exit 2
fi

if [ ! -d "$HERMES_DIR" ]; then
  echo "error: Hermes directory not found: $HERMES_DIR" >&2
  exit 2
fi

export HERMES_HOME

rm -rf "$INSTALL_SRC"
mkdir -p "$INSTALL_SRC"
cp -R "$SCRIPT_DIR/src" "$SCRIPT_DIR/skills" "$SCRIPT_DIR/pyproject.toml" "$INSTALL_SRC/"

"$PYTHON" - "$INSTALL_SRC/src" <<'PY'
import site
import sys
from pathlib import Path

src = Path(sys.argv[1]).resolve()
candidates = []
try:
    candidates.extend(site.getsitepackages())
except Exception:
    pass
try:
    candidates.append(site.getusersitepackages())
except Exception:
    pass

for raw in candidates:
    path = Path(raw)
    if path.exists():
        pth = path / "clawchat_gateway_src.pth"
        pth.write_text(
            "import sys; p = "
            + repr(str(src))
            + "; sys.path.remove(p) if p in sys.path else None; sys.path.insert(0, p)\n",
            encoding="utf-8",
        )
        print(f"registered python path: {pth} -> {src}")
        break
else:
    raise SystemExit("error: no writable site-packages directory found")
PY

"$PYTHON" "$INSTALL_SRC/src/clawchat_gateway/install.py" --hermes-dir "$HERMES_DIR"

cat <<EOF

ClawChat gateway installed.
Hermes home: $HERMES_HOME
Hermes dir:  $HERMES_DIR
Source dir:   $INSTALL_SRC

Restart Hermes gateway/container for the patched platform and ClawChat skill to load.
EOF
