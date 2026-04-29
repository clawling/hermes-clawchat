from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def _hermes_dir() -> Path:
    for key in ("HERMES_DIR", "HERMES_AGENT_DIR"):
        value = os.environ.get(key)
        if value:
            return Path(value)
    if Path("/opt/hermes/gateway").is_dir():
        return Path("/opt/hermes")
    return _hermes_home() / "hermes-agent"


def _hermes_binary(hermes_dir: Path) -> Path:
    candidates = [
        hermes_dir / ".venv" / "bin" / "hermes",
        Path.home() / ".hermes" / "hermes-agent" / ".venv" / "bin" / "hermes",
        Path("/opt/hermes/.venv/bin/hermes"),
    ]
    return next((path for path in candidates if path.exists()), Path("hermes"))


def schedule_gateway_restart(delay_seconds: int = 2) -> str:
    hermes_dir = _hermes_dir()
    hermes_home = _hermes_home()
    hermes_bin = _hermes_binary(hermes_dir)

    command = (
        f"sleep {int(delay_seconds)}; "
        f"HERMES_HOME={str(hermes_home)!r} "
        f"HERMES_DIR={str(hermes_dir)!r} "
        f"{str(hermes_bin)!r} gateway restart"
    )
    subprocess.Popen(
        ["sh", "-lc", command],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return command
