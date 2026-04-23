from __future__ import annotations

import logging
import os
import site
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _plugin_dir() -> Path:
    return Path(__file__).resolve().parent


def _hermes_dir() -> Path:
    for key in ("HERMES_DIR", "HERMES_AGENT_DIR"):
        value = os.environ.get(key)
        if value:
            return Path(value)
    if Path("/opt/hermes/gateway").is_dir():
        return Path("/opt/hermes")
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "hermes-agent"


def _register_python_path(src: Path) -> None:
    src_str = str(src.resolve())
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

    candidates: list[str] = []
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
        if not path.exists():
            continue
        pth = path / "clawchat_gateway_src.pth"
        pth.write_text(
            "import sys; p = "
            + repr(src_str)
            + "; sys.path.remove(p) if p in sys.path else None; sys.path.insert(0, p)\n",
            encoding="utf-8",
        )
        logger.info("ClawChat registered Python path: %s -> %s", pth, src)
        return
    raise RuntimeError("no writable site-packages directory found")


def _install_gateway() -> None:
    plugin_dir = _plugin_dir()
    src = plugin_dir / "src"
    _register_python_path(src)

    from clawchat_gateway.install import main as install_main

    hermes_dir = _hermes_dir()
    code = install_main(["--hermes-dir", str(hermes_dir)])
    if code != 0:
        raise RuntimeError(f"clawchat gateway install failed with exit code {code}")


def _tool_error(exc: Exception) -> dict:
    return {"ok": False, "error": str(exc), "kind": exc.__class__.__name__}


def _register_tools(ctx) -> None:
    activate_schema = {
        "name": "clawchat_activate",
        "description": (
            "Exchange a ClawChat activation code for token, refresh_token, and user_id, then persist "
            "them into Hermes config. Always use this when the user says a ClawChat activation code, "
            "for example `clawchat 的激活码是 R4E1IW`, `ClawChat激活码: R4E1IW`, or "
            "`activate clawchat R4E1IW`. Extract the code verbatim. Do not call connect-codes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "ClawChat activation code. For `clawchat 的激活码是 R4E1IW`, use `R4E1IW`.",
                },
                "baseUrl": {
                    "type": "string",
                    "description": "Optional ClawChat HTTP API base URL. Defaults to the NewBase ClawChat endpoint.",
                },
            },
            "required": ["code"],
        },
    }

    async def handle_activate(params):
        try:
            from clawchat_gateway.activate import activate
            from clawchat_gateway.api_client import DEFAULT_BASE_URL

            base_url = str(params.get("baseUrl") or "").strip() or DEFAULT_BASE_URL
            result = await activate(str(params.get("code") or "").strip(), base_url=base_url)
            result["ok"] = True
            return result
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool(
        "clawchat_activate",
        "clawchat",
        activate_schema,
        handle_activate,
        is_async=True,
        description="Activate ClawChat credentials from a user-provided activation code.",
        emoji="🔑",
    )

    nickname_schema = {
        "name": "clawchat_update_nickname",
        "description": "Update the ClawChat agent nickname/display name.",
        "parameters": {
            "type": "object",
            "properties": {
                "nickname": {"type": "string", "description": "New ClawChat nickname"}
            },
            "required": ["nickname"],
        },
    }

    async def handle_update_nickname(params):
        try:
            from clawchat_gateway.profile import update_nickname

            return await update_nickname(str(params.get("nickname") or ""))
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool(
        "clawchat_update_nickname",
        "clawchat",
        nickname_schema,
        handle_update_nickname,
        is_async=True,
        description="Update the ClawChat agent nickname.",
        emoji="🏷️",
    )

    avatar_schema = {
        "name": "clawchat_update_avatar",
        "description": (
            "Update the ClawChat agent avatar from an absolute local file path. "
            "This tool uploads the file first through `/v1/files/upload-url`, then updates "
            "the profile with the uploaded avatar URL. Do not pass HTTP URLs or relative paths."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "Absolute local path to the avatar image file",
                }
            },
            "required": ["filePath"],
        },
    }

    async def handle_update_avatar(params):
        try:
            from clawchat_gateway.profile import update_avatar

            return await update_avatar(str(params.get("filePath") or ""))
        except Exception as exc:
            return _tool_error(exc)

    ctx.register_tool(
        "clawchat_update_avatar",
        "clawchat",
        avatar_schema,
        handle_update_avatar,
        is_async=True,
        description="Upload a local avatar image first, then update the ClawChat profile avatar URL.",
        emoji="🖼️",
    )


def register(ctx) -> None:
    _register_python_path(_plugin_dir() / "src")
    _register_tools(ctx)

    skill = _plugin_dir() / "skills" / "clawchat" / "SKILL.md"
    if skill.exists():
        ctx.register_skill(
            "clawchat",
            skill,
            description="Activate and operate the ClawChat Hermes gateway integration.",
        )

    try:
        _install_gateway()
    except Exception as exc:
        logger.warning("Failed to auto-install ClawChat gateway plugin: %s", exc)
