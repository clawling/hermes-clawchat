"""Hermes plugin that registers ClawChat tool capabilities."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import yaml

from clawchat_gateway.api_client import (
    DEFAULT_BASE_URL,
    DEFAULT_WEBSOCKET_URL,
    ClawChatApiClient,
    ClawChatApiError,
)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _validation_error(message: str) -> dict:
    return {"error": message, "kind": "validation"}


def _tool_error(exc: Exception) -> dict:
    if isinstance(exc, ClawChatApiError):
        return {"error": exc.message, "kind": exc.kind}
    return {"error": str(exc), "kind": "transport"}


def _guess_mime(path: str) -> str:
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def _read_upload_file(path: str) -> tuple[bytes, str, str] | dict:
    if not path or not Path(path).is_absolute():
        return _validation_error("filePath must be an absolute local path")
    file_path = Path(path)
    try:
        stat = file_path.stat()
    except Exception as exc:
        return _validation_error(f"cannot stat {path}: {exc}")
    if not file_path.is_file():
        return _validation_error(f"{path} is not a regular file")
    if stat.st_size > MAX_UPLOAD_BYTES:
        return _validation_error(f"file too large ({stat.st_size} bytes; max 20MB)")
    return file_path.read_bytes(), file_path.name, _guess_mime(path)


def _load_plugin_config() -> tuple[Path, dict]:
    try:
        from hermes_cli.config import get_hermes_home
    except Exception:
        from pathlib import Path as _Path

        return _Path.home() / ".hermes" / "config.yaml", {}

    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return config_path, {}
    try:
        with open(config_path, encoding="utf-8") as handle:
            return config_path, yaml.safe_load(handle) or {}
    except Exception:
        return config_path, {}


def _write_plugin_config(config_path: Path, config: dict) -> None:
    try:
        from utils import atomic_yaml_write

        atomic_yaml_write(config_path, config)
        return
    except Exception:
        pass
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, allow_unicode=False, sort_keys=False)


def _derive_websocket_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.netloc in {"company.newbaselab.com:19001", "company.newbaselab.com:10086"}:
        return "ws://company.newbaselab.com:10086/ws"
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, "/v1/ws", "", "", ""))


def _get_clawchat_account() -> dict:
    _config_path, config = _load_plugin_config()
    platforms = config.get("platforms") or {}
    clawchat = platforms.get("clawchat") or {}
    extra = clawchat.get("extra") or {}
    return {
        "base_url": extra.get("base_url") or DEFAULT_BASE_URL,
        "websocket_url": extra.get("websocket_url") or DEFAULT_WEBSOCKET_URL,
        "token": extra.get("token") or "",
        "user_id": extra.get("user_id") or "",
    }


def _persist_activation(
    access_token: str,
    user_id: str,
    refresh_token: str | None,
    *,
    base_url: str | None = None,
) -> dict:
    config_path, config = _load_plugin_config()
    platforms = config.setdefault("platforms", {})
    clawchat = platforms.setdefault("clawchat", {})
    clawchat["enabled"] = True
    extra = clawchat.setdefault("extra", {})
    extra["base_url"] = (base_url or extra.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
    if base_url:
        extra["websocket_url"] = _derive_websocket_url(extra["base_url"])
    else:
        extra.setdefault("websocket_url", DEFAULT_WEBSOCKET_URL)
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
    _write_plugin_config(config_path, config)
    return extra


def _client(*, base_url: str | None = None) -> ClawChatApiClient:
    account = _get_clawchat_account()
    return ClawChatApiClient(
        base_url=(base_url or account["base_url"]).rstrip("/"),
        token=account["token"],
        user_id=account["user_id"],
    )


def _media_client() -> ClawChatApiClient:
    account = _get_clawchat_account()
    parsed = urlparse(account["websocket_url"])
    if parsed.scheme in {"ws", "wss"} and parsed.netloc:
        scheme = "https" if parsed.scheme == "wss" else "http"
        base_url = urlunparse((scheme, parsed.netloc, "", "", "", ""))
    else:
        base_url = account["base_url"]
    return ClawChatApiClient(
        base_url=base_url.rstrip("/"),
        token=account["token"],
        user_id=account["user_id"],
    )


def register(ctx):
    activate_schema = {
        "name": "clawchat_activate",
        "description": (
            "Exchange a ClawChat invite code for credentials and persist the resulting token so Hermes "
            "can connect to ClawChat. Always call this tool when the user says a ClawChat activation "
            "code, including Chinese phrases like 'clawchat 的激活码是 R4E1IW', 'ClawChat激活码: "
            "R4E1IW', '激活 clawchat R4E1IW', or English phrases like 'clawchat INV-ABC123', "
            "'activate clawchat', or 'use invite code XYZ'. If the user asks to activate or set up "
            "ClawChat but does not provide a code yet, ask them to provide the activation code before "
            "calling this tool. Extract the code verbatim; for "
            "'clawchat 的激活码是 R4E1IW', call with code = \"R4E1IW\". Do not ask for baseUrl; "
            "the default ClawChat endpoints are already configured unless the user explicitly provides "
            "a different baseUrl. After this tool succeeds, tell the user Hermes must be restarted for "
            "the new ClawChat credentials to take effect."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Invite/activation code. For 'clawchat 的激活码是 R4E1IW', use R4E1IW.",
                },
                "baseUrl": {
                    "type": "string",
                    "description": "Optional HTTP API root override, e.g. https://api.example.com",
                },
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tool names to register or grant during activation.",
                },
            },
            "required": ["code"],
        },
    }

    async def handle_activate(params):
        try:
            base_url = str(params.get("baseUrl", "") or "").strip() or None
            tools = params.get("tools")
            result = await _client(base_url=base_url).agents_connect(
                code=str(params.get("code", "")),
                tools=tools if isinstance(tools, list) else None,
            )
            extra = _persist_activation(
                access_token=str(result["access_token"]),
                user_id=str(result["agent"]["user_id"]),
                refresh_token=result.get("refresh_token"),
                base_url=base_url,
            )
            return {
                "ok": True,
                "token": "***",
                "refresh_token": "***" if result.get("refresh_token") else None,
                "user_id": extra["user_id"],
                "base_url": extra["base_url"],
                "websocket_url": extra["websocket_url"],
                "restart_required": True,
                "restart_message": (
                    "ClawChat activation is saved. Restart Hermes gateway so the running ClawChat "
                    "connection reloads token, refresh_token, user_id, and websocket settings."
                ),
            }
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool("clawchat_activate", "clawchat", activate_schema, handle_activate, is_async=True)

    get_my_profile_schema = {
        "name": "clawchat_get_my_profile",
        "description": "Fetch this agent's own ClawChat profile.",
        "parameters": {"type": "object", "properties": {}},
    }

    async def handle_get_my_profile(_params):
        try:
            return await _client().get_my_profile()
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool(
        "clawchat_get_my_profile", "clawchat", get_my_profile_schema, handle_get_my_profile, is_async=True
    )

    get_user_info_schema = {
        "name": "clawchat_get_user_info",
        "description": "Fetch a ClawChat user profile by userId.",
        "parameters": {
            "type": "object",
            "properties": {"userId": {"type": "string", "description": "Target user id"}},
            "required": ["userId"],
        },
    }

    async def handle_get_user_info(params):
        try:
            return await _client().get_user_info(str(params.get("userId", "")))
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool(
        "clawchat_get_user_info", "clawchat", get_user_info_schema, handle_get_user_info, is_async=True
    )

    list_friends_schema = {
        "name": "clawchat_list_friends",
        "description": "List the agent's ClawChat friends with pagination.",
        "parameters": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "minimum": 1, "description": "1-based page number"},
                "pageSize": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Page size 1..100",
                },
            },
        },
    }

    async def handle_list_friends(params):
        try:
            return await _client().list_friends(
                page=int(params.get("page", 1) or 1),
                page_size=int(params.get("pageSize", 20) or 20),
            )
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool(
        "clawchat_list_friends", "clawchat", list_friends_schema, handle_list_friends, is_async=True
    )

    update_profile_schema = {
        "name": "clawchat_update_my_profile",
        "description": (
            "Update this agent's own ClawChat profile. Use for nickname changes, avatar updates, "
            "or bio/self-introduction edits. When using a local image for avatar, call "
            "`clawchat_upload_avatar` first and pass its URL as `avatar_url`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nickname": {"type": "string", "description": "New nickname"},
                "avatar_url": {"type": "string", "description": "Uploaded avatar URL"},
                "bio": {"type": "string", "description": "New self-introduction"},
            },
        },
    }

    async def handle_update_profile(params):
        try:
            return await _client().update_my_profile(
                nickname=params.get("nickname"),
                avatar_url=params.get("avatar_url"),
                bio=params.get("bio"),
            )
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool(
        "clawchat_update_my_profile", "clawchat", update_profile_schema, handle_update_profile, is_async=True
    )

    upload_avatar_schema = {
        "name": "clawchat_upload_avatar",
        "description": "Upload a local avatar image to ClawChat avatar storage (max 20MB).",
        "parameters": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string", "description": "Absolute local path to avatar image"}
            },
            "required": ["filePath"],
        },
    }

    async def handle_upload_avatar(params):
        loaded = _read_upload_file(str(params.get("filePath", "")))
        if isinstance(loaded, dict):
            return loaded
        buffer, filename, mime = loaded
        try:
            result = await _client().upload_avatar(buffer=buffer, filename=filename, mime=mime)
            return {"url": result.url, "size": result.size, "mime": result.mime}
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool(
        "clawchat_upload_avatar", "clawchat", upload_avatar_schema, handle_upload_avatar, is_async=True
    )

    upload_file_schema = {
        "name": "clawchat_upload_file",
        "description": "Upload a local file to ClawChat media storage (max 20MB).",
        "parameters": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string", "description": "Absolute local path to file"}
            },
            "required": ["filePath"],
        },
    }

    async def handle_upload_file(params):
        loaded = _read_upload_file(str(params.get("filePath", "")))
        if isinstance(loaded, dict):
            return loaded
        buffer, filename, mime = loaded
        try:
            result = await _media_client().upload_media(buffer=buffer, filename=filename, mime=mime)
            return {"url": result.url, "size": result.size, "mime": result.mime}
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool(
        "clawchat_upload_file", "clawchat", upload_file_schema, handle_upload_file, is_async=True
    )
