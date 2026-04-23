from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from clawchat_gateway.api_client import DEFAULT_BASE_URL, ClawChatApiClient, ClawChatApiError

MAX_AVATAR_BYTES = 20 * 1024 * 1024


class ProfileConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ProfileConfig:
    base_url: str
    token: str
    user_id: str
    config_path: Path


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ProfileConfigError(f"config.yaml not found at {path}; activate ClawChat first")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise ProfileConfigError(f"failed to read {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ProfileConfigError(f"invalid config.yaml at {path}: expected object")
    return loaded


def load_profile_config() -> ProfileConfig:
    config_path = _hermes_home() / "config.yaml"
    config = _load_yaml(config_path)
    extra = (
        config.get("platforms", {})
        .get("clawchat", {})
        .get("extra", {})
    )
    if not isinstance(extra, dict):
        extra = {}

    base_url = str(extra.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
    token = str(extra.get("token") or "").strip()
    user_id = str(extra.get("user_id") or "").strip()
    if not token:
        raise ProfileConfigError("missing platforms.clawchat.extra.token; activate ClawChat first")
    if not user_id:
        raise ProfileConfigError("missing platforms.clawchat.extra.user_id; activate ClawChat first")
    return ProfileConfig(base_url=base_url, token=token, user_id=user_id, config_path=config_path)


def _client(config: ProfileConfig) -> ClawChatApiClient:
    return ClawChatApiClient(base_url=config.base_url, token=config.token, user_id=config.user_id)


async def update_nickname(nickname: str) -> dict[str, Any]:
    nickname = nickname.strip()
    if not nickname:
        raise ProfileConfigError("nickname is required")
    config = load_profile_config()
    profile = await _client(config).update_my_profile(nickname=nickname)
    return {
        "ok": True,
        "config_path": str(config.config_path),
        "user_id": config.user_id,
        "updated": {"nickname": nickname},
        "profile": profile,
    }


def _avatar_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ProfileConfigError("avatar path must be an absolute local file path")
    if not path.exists():
        raise ProfileConfigError(f"avatar file does not exist: {path}")
    if not path.is_file():
        raise ProfileConfigError(f"avatar path is not a file: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise ProfileConfigError(f"avatar file is empty: {path}")
    if size > MAX_AVATAR_BYTES:
        raise ProfileConfigError(f"avatar file exceeds {MAX_AVATAR_BYTES} bytes: {path}")
    return path


async def update_avatar(path: str) -> dict[str, Any]:
    avatar_path = _avatar_path(path)
    config = load_profile_config()
    mime = mimetypes.guess_type(str(avatar_path))[0] or "application/octet-stream"
    client = _client(config)
    uploaded = await client.upload_avatar(
        buffer=avatar_path.read_bytes(),
        filename=avatar_path.name,
        mime=mime,
    )
    profile = await client.update_my_profile(avatar_url=uploaded.url)
    return {
        "ok": True,
        "config_path": str(config.config_path),
        "user_id": config.user_id,
        "uploaded": {"url": uploaded.url, "size": uploaded.size, "mime": uploaded.mime},
        "updated": {"avatar_url": uploaded.url},
        "profile": profile,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m clawchat_gateway.profile")
    subparsers = parser.add_subparsers(dest="command", required=True)

    nickname_parser = subparsers.add_parser("nickname", help="Update the ClawChat agent nickname")
    nickname_parser.add_argument("nickname")

    avatar_parser = subparsers.add_parser("avatar", help="Upload and set the ClawChat agent avatar")
    avatar_parser.add_argument("path", help="Absolute local avatar file path")

    args = parser.parse_args(argv)
    try:
        if args.command == "nickname":
            payload = asyncio.run(update_nickname(args.nickname))
        elif args.command == "avatar":
            payload = asyncio.run(update_avatar(args.path))
        else:
            parser.error(f"unknown command: {args.command}")
    except (ProfileConfigError, ClawChatApiError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
