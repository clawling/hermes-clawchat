from __future__ import annotations

import importlib
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
    from clawchat_gateway.install import main as install_main

    hermes_dir = _hermes_dir()
    code = install_main(["--hermes-dir", str(hermes_dir)])
    if code != 0:
        raise RuntimeError(f"clawchat gateway install failed with exit code {code}")

    _refresh_gateway_module_cache()


_GATEWAY_MODULES_TO_REFRESH = (
    "gateway.config",
    "gateway.run",
    # Also the adapter: it does ``from gateway.config import Platform`` at
    # module scope, so if anything imports it before register() has applied
    # the patch (e.g. a consumer that does ``import clawchat_gateway.adapter``
    # directly), its bound ``Platform`` is stale even after we reload
    # ``gateway.config``. Reloading the adapter re-binds it from the fresh
    # enum.
    "clawchat_gateway.adapter",
)


def _refresh_gateway_module_cache() -> None:
    """Ensure patched gateway modules are picked up by later imports.

    Plugin discovery can run after hermes-agent's CLI has already imported
    ``gateway.config`` (e.g. to validate the loaded config). Our file patch
    won't take effect unless we invalidate the import caches and reload any
    gateway module that was imported before we patched it on disk, otherwise
    ``gateway.run`` resolves ``Platform.CLAWCHAT`` against a stale enum.
    """
    importlib.invalidate_caches()
    for mod_name in _GATEWAY_MODULES_TO_REFRESH:
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        try:
            importlib.reload(mod)
        except Exception as exc:
            logger.error(
                "ClawChat could not reload %s after patching; existing "
                "references to its symbols may be stale: %s",
                mod_name,
                exc,
            )


def _tool_error(exc: Exception) -> dict:
    return {"ok": False, "error": str(exc), "kind": exc.__class__.__name__}


async def _handle_clawchat_activate(args, **kw):
    task_id = kw.get("task_id") or "default"
    _handle_clawchat_activate._last_task_id = task_id
    logger.info("clawchat_activate start task_id=%s", task_id)
    try:
        from clawchat_gateway.activate import activate
        from clawchat_gateway.api_client import DEFAULT_BASE_URL
        from clawchat_gateway.restart import schedule_gateway_restart

        base_url = str(args.get("baseUrl") or "").strip() or DEFAULT_BASE_URL
        result = await activate(str(args.get("code") or "").strip(), base_url=base_url)
        result["ok"] = True
        restart_command = schedule_gateway_restart(delay_seconds=2)
        result["restart_scheduled"] = True
        result["restart_delay_seconds"] = 2
        result["restart_message"] = "ClawChat activation is saved. Hermes restart has been scheduled in the background."
        logger.info("clawchat_activate done task_id=%s user_id=%s", task_id, result.get("user_id"))
        logger.info("clawchat_activate scheduled restart task_id=%s command=%s", task_id, restart_command)
        return result
    except Exception as exc:
        logger.warning("clawchat_activate failed task_id=%s error=%s", task_id, exc)
        return _tool_error(exc)


async def _handle_clawchat_get_account_profile(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_get_account_profile start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.get_account_profile()
    logger.info("clawchat_get_account_profile done task_id=%s", task_id)
    return result


async def _handle_clawchat_get_user_profile(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_get_user_profile start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.get_user_profile(str(args.get("userId") or ""))
    logger.info("clawchat_get_user_profile done task_id=%s", task_id)
    return result


def _optional_int_arg(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


async def _handle_clawchat_list_account_friends(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_list_account_friends start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.list_account_friends(
        page=_optional_int_arg(args.get("page")),
        page_size=_optional_int_arg(args.get("pageSize")),
    )
    logger.info("clawchat_list_account_friends done task_id=%s", task_id)
    return result


async def _handle_clawchat_update_account_profile(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_update_account_profile start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.update_account_profile(
        nickname=args.get("nickname") if isinstance(args.get("nickname"), str) else None,
        avatar_url=args.get("avatar_url") if isinstance(args.get("avatar_url"), str) else None,
        bio=args.get("bio") if isinstance(args.get("bio"), str) else None,
    )
    logger.info("clawchat_update_account_profile done task_id=%s", task_id)
    return result


async def _handle_clawchat_upload_avatar_image(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_upload_avatar_image start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.upload_avatar_image(str(args.get("filePath") or ""))
    logger.info("clawchat_upload_avatar_image done task_id=%s", task_id)
    return result


async def _handle_clawchat_upload_media_file(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_upload_media_file start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.upload_media_file(str(args.get("filePath") or ""))
    logger.info("clawchat_upload_media_file done task_id=%s", task_id)
    return result


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

    ctx.register_tool(
        "clawchat_activate",
        "clawchat",
        activate_schema,
        _handle_clawchat_activate,
        is_async=True,
        description="Activate ClawChat credentials from a user-provided activation code.",
        emoji="🔑",
    )

    ctx.register_tool(
        "clawchat_get_account_profile",
        "clawchat",
        {
            "name": "clawchat_get_account_profile",
            "description": (
                "Fetch the configured ClawChat account profile (user id, nickname/display name, avatar, bio). "
                "TRIGGER — invoke when the user asks for the ClawChat account/profile connected to this plugin, "
                "such as 'show my ClawChat profile', 'what is the configured ClawChat account?', "
                "'当前 ClawChat 账号资料', or 'ClawChat 昵称头像简介'. "
                "Do not use this for OpenClaw agent persona/profile questions unless the user explicitly means the ClawChat account."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
        _handle_clawchat_get_account_profile,
        is_async=True,
        description="Get ClawChat Account Profile",
        emoji="👤",
    )

    ctx.register_tool(
        "clawchat_get_user_profile",
        "clawchat",
        {
            "name": "clawchat_get_user_profile",
            "description": (
                "Fetch a ClawChat user's public profile by userId. "
                "TRIGGER — invoke when the user asks to look up, view, or inspect a specific ClawChat user's public profile "
                "and provides a concrete userId. Do not guess or infer userId from a nickname/display name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "userId": {
                        "type": "string",
                        "description": "ClawChat user id (required, must be explicit)",
                    },
                },
                "required": ["userId"],
            },
        },
        _handle_clawchat_get_user_profile,
        is_async=True,
        description="Get ClawChat User Profile",
        emoji="🧑",
    )

    ctx.register_tool(
        "clawchat_list_account_friends",
        "clawchat",
        {
            "name": "clawchat_list_account_friends",
            "description": (
                "List the configured ClawChat account's friends/contacts, paginated (page=1, pageSize=20 by default). "
                "TRIGGER — invoke when the user asks for this ClawChat account's friends, contacts, friend list, "
                "or asks to show more friends with pagination."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "minimum": 1, "description": "1-based page index"},
                    "pageSize": {"type": "integer", "minimum": 1, "maximum": 100, "description": "1..100"},
                },
            },
        },
        _handle_clawchat_list_account_friends,
        is_async=True,
        description="List ClawChat Account Friends",
        emoji="👥",
    )

    ctx.register_tool(
        "clawchat_update_account_profile",
        "clawchat",
        {
            "name": "clawchat_update_account_profile",
            "description": (
                "Update the configured ClawChat account profile (nickname and/or avatar_url and/or bio). "
                "TRIGGER — invoke this tool whenever the user's message explicitly asks to change the ClawChat account profile: "
                "(1) ClawChat account nickname/name change: 'change the ClawChat account nickname to X', "
                "'set this ClawChat account name to X', 'ClawChat 昵称改为 X', '账号昵称改成 X', '账号名字叫 X' "
                "→ call with `nickname = X`; "
                "(2) ClawChat account avatar/profile-picture change: 'change the ClawChat account avatar', "
                "'use this image as the ClawChat profile picture', 'ClawChat 头像改为 …', '账号头像换成 …' "
                "→ first obtain the avatar URL (upload via `clawchat_upload_avatar_image`, OR use a provided URL directly), "
                "then call this tool with `avatar_url = <url>`; "
                "(3) ClawChat account bio/self-introduction change: 'update the ClawChat bio', "
                "'set the ClawChat account self-introduction to X', 'ClawChat 简介改成 X', '账号简介改为 X', '个人简介改为 X' "
                "→ call with `bio = X`. "
                "You can pass `nickname`, `avatar_url`, and `bio` together in one call, or just one of them. "
                "At least one of the three must be present. Do not use this for OpenClaw agent persona changes unless the user explicitly refers to the ClawChat account."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nickname": {"type": "string", "description": "New ClawChat account nickname/display name"},
                    "avatar_url": {"type": "string", "description": "Hosted avatar image URL"},
                    "bio": {"type": "string", "description": "New ClawChat account bio/self-introduction"},
                },
            },
        },
        _handle_clawchat_update_account_profile,
        is_async=True,
        description="Update ClawChat Account Profile",
        emoji="✏️",
    )

    ctx.register_tool(
        "clawchat_upload_avatar_image",
        "clawchat",
        {
            "name": "clawchat_upload_avatar_image",
            "description": (
                "Upload a local image file to ClawChat avatar storage (max 20MB) and return the hosted avatar URL. "
                "TRIGGER — invoke when the user provides an absolute local image path and asks to upload it for the ClawChat account avatar/profile picture. "
                "This tool does not update or set the account avatar by itself; call `clawchat_update_account_profile` with `avatar_url` after this tool returns a URL."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "Absolute local path to the avatar image file"},
                },
                "required": ["filePath"],
            },
        },
        _handle_clawchat_upload_avatar_image,
        is_async=True,
        description="Upload ClawChat Avatar Image",
        emoji="🖼️",
    )

    ctx.register_tool(
        "clawchat_upload_media_file",
        "clawchat",
        {
            "name": "clawchat_upload_media_file",
            "description": (
                "Upload a local file or media file to ClawChat media storage (max 20MB) and return the public URL/shareable URL. "
                "TRIGGER — invoke when the user provides an absolute local file path and asks to upload, share, or create a ClawChat-accessible link for that file. "
                "Do not use this for account avatar changes; use `clawchat_upload_avatar_image` for avatar images."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "Absolute local path to the file to upload"},
                },
                "required": ["filePath"],
            },
        },
        _handle_clawchat_upload_media_file,
        is_async=True,
        description="Upload ClawChat Media File",
        emoji="📎",
    )


def register(ctx) -> None:
    _register_python_path(_plugin_dir() / "src")

    try:
        _install_gateway()
    except Exception as exc:
        logger.error(
            "ClawChat gateway auto-install failed; skipping tool/skill "
            "registration to avoid leaving hermes-agent in a partially "
            "patched state: %s",
            exc,
        )
        raise

    _register_tools(ctx)

    skill = _plugin_dir() / "skills" / "clawchat" / "SKILL.md"
    if skill.exists():
        ctx.register_skill(
            "clawchat",
            skill,
            description="Activate and operate the ClawChat Hermes gateway integration.",
        )
