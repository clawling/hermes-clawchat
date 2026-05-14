from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def _tool_error(exc: Exception) -> dict:
    return {"ok": False, "error": str(exc), "kind": exc.__class__.__name__}


def _tool_result(payload: dict) -> str:
    """Return a Hermes v0.12-compatible tool result string."""
    return json.dumps(payload, ensure_ascii=False)


async def handle_clawchat_activate(args, **kw):
    task_id = kw.get("task_id") or "default"
    handle_clawchat_activate._last_task_id = task_id
    logger.info("clawchat_activate start task_id=%s", task_id)
    try:
        from clawchat_gateway.activate import activate_and_maybe_restart
        from clawchat_gateway.api_client import DEFAULT_BASE_URL

        base_url = str(args.get("baseUrl") or "").strip() or DEFAULT_BASE_URL
        result = await activate_and_maybe_restart(
            str(args.get("code") or "").strip(),
            base_url=base_url,
            restart=True,
        )
        logger.info("clawchat_activate done task_id=%s user_id=%s", task_id, result.get("user_id"))
        logger.info(
            "clawchat_activate scheduled restart task_id=%s command=%s",
            task_id,
            result.get("restart_command"),
        )
        return _tool_result(result)
    except Exception as exc:
        logger.warning("clawchat_activate failed task_id=%s error=%s", task_id, exc)
        return _tool_result(_tool_error(exc))


async def handle_clawchat_get_account_profile(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_get_account_profile start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.get_account_profile()
    logger.info("clawchat_get_account_profile done task_id=%s", task_id)
    return _tool_result(result)


async def handle_clawchat_get_user_profile(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_get_user_profile start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.get_user_profile(str(args.get("userId") or ""))
    logger.info("clawchat_get_user_profile done task_id=%s", task_id)
    return _tool_result(result)


def _optional_int_arg(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


async def handle_clawchat_list_account_friends(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_list_account_friends start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.list_account_friends(
        page=_optional_int_arg(args.get("page")),
        page_size=_optional_int_arg(args.get("pageSize")),
    )
    logger.info("clawchat_list_account_friends done task_id=%s", task_id)
    return _tool_result(result)


async def handle_clawchat_update_account_profile(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_update_account_profile start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.update_account_profile(
        nickname=args.get("nickname") if isinstance(args.get("nickname"), str) else None,
        avatar_url=args.get("avatar_url") if isinstance(args.get("avatar_url"), str) else None,
        bio=args.get("bio") if isinstance(args.get("bio"), str) else None,
    )
    logger.info("clawchat_update_account_profile done task_id=%s", task_id)
    return _tool_result(result)


async def handle_clawchat_upload_avatar_image(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_upload_avatar_image start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.upload_avatar_image(str(args.get("filePath") or ""))
    logger.info("clawchat_upload_avatar_image done task_id=%s", task_id)
    return _tool_result(result)


async def handle_clawchat_upload_media_file(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_upload_media_file start task_id=%s", task_id)
    from clawchat_gateway import tools

    result = await tools.upload_media_file(str(args.get("filePath") or ""))
    logger.info("clawchat_upload_media_file done task_id=%s", task_id)
    return _tool_result(result)


_DIRECT_TOOL_USE_INSTRUCTION = (
    "Use this registered ClawChat plugin tool directly. Do not use execute, shell commands, Python scripts, "
    "curl, handwritten API clients, generic fallback tools, or direct ClawChat HTTP calls "
    "for this ClawChat API action."
)


def _direct_tool_description(description: str) -> str:
    return description + " " + _DIRECT_TOOL_USE_INSTRUCTION


def register_tools(ctx) -> None:
    activate_schema = {
        "name": "clawchat_activate",
        "description": _direct_tool_description(
            "Exchange a ClawChat activation/invite code for credentials for the agent's connected "
            "ClawChat account, then persist credentials in this runtime's config. Always use this when "
            "the user says a ClawChat activation/invite code or asks to activate, connect, bind, or log in ClawChat. "
            "Examples include `clawchat 的激活码是 R4E1IW`, `ClawChat激活码: R4E1IW`, and `activate clawchat R4E1IW`. "
            "Extract the code verbatim. Do not normalize, lowercase, add prefixes, or invent a code. "
            "If activation intent lacks a code, ask for the activation/invite code before calling this tool. Do not call connect-codes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The ClawChat activation/invite code (six uppercase letters/digits, e.g. 'A1B2C3') extracted verbatim from the user's message for the agent's connected ClawChat account. For `clawchat 的激活码是 R4E1IW`, use `R4E1IW`. Whitespace is trimmed automatically; ask for the code if activation intent lacks one.",
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
        handle_clawchat_activate,
        is_async=True,
        description="Activate ClawChat credentials from a user-provided activation code.",
        emoji="🔑",
    )

    ctx.register_tool(
        "clawchat_get_account_profile",
        "clawchat",
        {
            "name": "clawchat_get_account_profile",
            "description": _direct_tool_description(
                "Fetch the agent's connected ClawChat account profile (the configured ClawChat account: user id, nickname/display name, avatar, bio). "
                "This profile is the platform-side mirror of the local assistant identity; if fields are missing, report them as unset instead of inventing values. "
                "TRIGGER — invoke when the user asks for the ClawChat account/profile connected to this agent, "
                "such as 'show my ClawChat profile', 'what is the configured ClawChat account?', "
                "'当前 ClawChat 账号资料', or 'ClawChat 昵称头像简介'. "
                "Do not frame this as a human user's personal account."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
        handle_clawchat_get_account_profile,
        is_async=True,
        description="Get ClawChat Account Profile",
        emoji="👤",
    )

    ctx.register_tool(
        "clawchat_get_user_profile",
        "clawchat",
        {
            "name": "clawchat_get_user_profile",
            "description": _direct_tool_description(
                "Fetch a ClawChat user's public profile by userId. "
                "TRIGGER — invoke when the user asks to look up, view, or inspect a specific ClawChat user's public profile "
                "and provides a concrete userId. Do not guess or infer userId from a nickname/display name. "
                "Use `clawchat_get_account_profile` for the agent's own connected ClawChat account unless an explicit userId is provided."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "userId": {
                        "type": "string",
                        "description": "Explicit target ClawChat user id (required). Do not infer this from a nickname; use clawchat_get_account_profile for the agent's own connected ClawChat account unless an explicit userId is provided.",
                    },
                },
                "required": ["userId"],
            },
        },
        handle_clawchat_get_user_profile,
        is_async=True,
        description="Get ClawChat User Profile",
        emoji="🧑",
    )

    ctx.register_tool(
        "clawchat_list_account_friends",
        "clawchat",
        {
            "name": "clawchat_list_account_friends",
            "description": _direct_tool_description(
                "List friends/contacts of the agent's connected ClawChat account (the configured ClawChat account), paginated (page=1, pageSize=20 by default). "
                "These are the agent's ClawChat-platform contacts. "
                "TRIGGER — invoke when the user asks for this ClawChat account's friends, contacts, friend list, or asks to show more friends with pagination."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "minimum": 1, "description": "1-based page number for the agent's connected ClawChat account friends (default 1)"},
                    "pageSize": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Page size 1..100 for the agent's ClawChat-platform contacts (default 20)"},
                },
            },
        },
        handle_clawchat_list_account_friends,
        is_async=True,
        description="List ClawChat Account Friends",
        emoji="👥",
    )

    ctx.register_tool(
        "clawchat_update_account_profile",
        "clawchat",
        {
            "name": "clawchat_update_account_profile",
            "description": _direct_tool_description(
                "Update nickname/avatar_url/bio on the agent's connected ClawChat account (the configured ClawChat account), which mirrors the local assistant identity. "
                "TRIGGER — invoke this tool whenever the user's message asks to change the ClawChat account profile or local assistant name/profile while ClawChat is connected: "
                "(1) ClawChat account nickname/name change: 'change the ClawChat account nickname to X', "
                "'set this assistant name to X', 'ClawChat 昵称改为 X', '账号昵称改成 X', '账号名字叫 X' "
                "→ call with `nickname = X`; "
                "(2) ClawChat account avatar/profile-picture change: 'change the ClawChat account avatar', "
                "'use this image as the assistant profile picture', 'ClawChat 头像改为 …', '账号头像换成 …' "
                "→ first obtain the avatar URL (upload via `clawchat_upload_avatar_image`, OR use a provided URL directly), "
                "then call this tool with `avatar_url = <url>`; "
                "(3) ClawChat account bio/self-introduction change: 'update the ClawChat bio', "
                "'set the assistant self-introduction to X', 'ClawChat 简介改成 X', '账号简介改为 X', '个人简介改为 X' "
                "→ call with `bio = X`. "
                "You can pass `nickname`, `avatar_url`, and `bio` together in one call, or just one of them. "
                "At least one of the three must be present. Do not frame this as updating a human user's personal account."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nickname": {"type": "string", "description": "New nickname/display name for the agent's connected ClawChat account, mirroring the local assistant identity"},
                    "avatar_url": {"type": "string", "description": "Avatar URL for the agent's connected ClawChat account profile (use clawchat_upload_avatar_image first to obtain one from a local image)"},
                    "bio": {"type": "string", "description": "New self-introduction / bio text for the agent's connected ClawChat account, mirroring the local assistant identity"},
                },
            },
        },
        handle_clawchat_update_account_profile,
        is_async=True,
        description="Update ClawChat Account Profile",
        emoji="✏️",
    )

    ctx.register_tool(
        "clawchat_upload_avatar_image",
        "clawchat",
        {
            "name": "clawchat_upload_avatar_image",
            "description": _direct_tool_description(
                "Upload an absolute local image path for use as the agent's connected ClawChat account avatar (max 20MB), returning a hosted avatar URL. "
                "TRIGGER — invoke when the user provides an absolute local image path and asks to upload it for the ClawChat account avatar/profile picture. "
                "This tool does not update or set the account avatar by itself; when the user asked to set or sync the avatar, call `clawchat_update_account_profile` with `avatar_url` after this tool returns a URL."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "Absolute local path of the avatar image to upload for the agent's connected ClawChat account (max 20MB)"},
                },
                "required": ["filePath"],
            },
        },
        handle_clawchat_upload_avatar_image,
        is_async=True,
        description="Upload ClawChat Avatar Image",
        emoji="🖼️",
    )

    ctx.register_tool(
        "clawchat_upload_media_file",
        "clawchat",
        {
            "name": "clawchat_upload_media_file",
            "description": _direct_tool_description(
                "Upload an absolute local file/media path to ClawChat media storage (max 20MB) and return a ClawChat-accessible public/shareable URL. "
                "TRIGGER — invoke when the user provides an absolute local file path and asks to upload, share, or create a ClawChat-accessible link for that file. "
                "Do not use this tool to send an attachment in the current chat; use the current runtime's native media-send mechanism instead (for example, MEDIA:/absolute/local/path where supported). "
                "Do not use this for account avatar changes; use `clawchat_upload_avatar_image` for avatar images. Do not use this just to mirror local assistant identity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "Absolute local path of the non-avatar media/file to upload to ClawChat for a ClawChat-accessible URL (max 20MB)"},
                },
                "required": ["filePath"],
            },
        },
        handle_clawchat_upload_media_file,
        is_async=True,
        description="Upload ClawChat Media File",
        emoji="📎",
    )
