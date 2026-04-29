from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import yaml

from clawchat_gateway.api_client import DEFAULT_BASE_URL, DEFAULT_WEBSOCKET_URL, ClawChatApiClient


def _hermes_home() -> Path:
    import os

    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def _load_config() -> tuple[Path, dict[str, Any]]:
    config_path = _hermes_home() / "config.yaml"
    if not config_path.exists():
        return config_path, {}
    try:
        return config_path, yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return config_path, {}


def _write_config(config_path: Path, config: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(config, allow_unicode=False, sort_keys=False),
        encoding="utf-8",
    )


def _derive_websocket_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.netloc in {"company.newbaselab.com:19001", "company.newbaselab.com:10086"}:
        return DEFAULT_WEBSOCKET_URL
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, "/v1/ws", "", "", ""))


def persist_activation(
    *,
    access_token: str,
    user_id: str,
    refresh_token: str | None,
    base_url: str,
) -> dict[str, Any]:
    config_path, config = _load_config()
    platforms = config.setdefault("platforms", {})
    clawchat = platforms.setdefault("clawchat", {})
    clawchat["enabled"] = True
    extra = clawchat.setdefault("extra", {})
    extra["base_url"] = base_url.rstrip("/")
    extra["websocket_url"] = _derive_websocket_url(extra["base_url"])
    extra["token"] = access_token
    extra["user_id"] = user_id
    extra["reply_mode"] = "stream"
    extra["show_tools_output"] = False
    extra["show_think_output"] = False
    if refresh_token:
        extra["refresh_token"] = refresh_token

    streaming = config.setdefault("streaming", {})
    streaming["enabled"] = True
    streaming.setdefault("transport", "edit")
    streaming.setdefault("edit_interval", 0.25)
    streaming.setdefault("buffer_threshold", 16)

    display = config.setdefault("display", {})
    display_platforms = display.setdefault("platforms", {})
    clawchat_display = display_platforms.setdefault("clawchat", {})
    clawchat_display["tool_progress"] = "off"
    clawchat_display["show_reasoning"] = False

    _write_config(config_path, config)
    return {
        "config_path": str(config_path),
        "user_id": user_id,
        "base_url": extra["base_url"],
        "websocket_url": extra["websocket_url"],
        "token": "***",
        "refresh_token": "***" if refresh_token else None,
        "restart_required": True,
        "restart_message": "Restart Hermes gateway so ClawChat reloads the new credentials.",
    }


async def activate(code: str, *, base_url: str) -> dict[str, Any]:
    client = ClawChatApiClient(base_url=base_url.rstrip("/"), token="", user_id="")
    result = await client.agents_connect(code=code)
    return persist_activation(
        access_token=str(result["access_token"]),
        user_id=str(result["agent"]["user_id"]),
        refresh_token=result.get("refresh_token"),
        base_url=base_url,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m clawchat_gateway.activate")
    parser.add_argument("code", help="ClawChat activation code")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Skip the detached `hermes gateway restart` dispatched after activation.",
    )
    args = parser.parse_args(argv)
    payload = asyncio.run(activate(args.code.strip(), base_url=args.base_url))
    if not args.no_restart:
        from clawchat_gateway.restart import schedule_gateway_restart

        payload["restart_scheduled"] = True
        payload["restart_delay_seconds"] = 2
        payload["restart_command"] = schedule_gateway_restart(delay_seconds=2)
        payload["restart_message"] = (
            "ClawChat activation saved. Hermes gateway restart dispatched in the background."
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
