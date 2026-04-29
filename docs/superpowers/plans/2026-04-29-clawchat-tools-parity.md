# ClawChat Tools Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **NOTE:** In the Multica context, this plan is dispatched to specialist agents (`Backend-Dev`, `QA`, `Tech-Writer`) via `multica issue create`, not via in-process subagents. Each phase below maps to one Multica child issue.

**Goal:** Bring `hermes-clawchat`'s ClawChat tool surface in line with `openclaw-clawchat` (6 new tools + retain `clawchat_activate`), rework the `python -m clawchat_gateway.profile` CLI to match, and refresh the docs.

**Architecture:** New `tools.py` module owns the 6 tool handlers and is the single source of truth for both the Hermes tool registrations (in `__init__.py`) and the CLI subcommands (in `profile.py`). All handlers return result dicts (no raises); the CLI inspects `result.get("error")` to decide stdout-vs-stderr and exit code.

**Tech Stack:** Python 3 (asyncio, argparse), pytest + pytest-asyncio, urllib.request (already in `api_client.py`), pyyaml.

**Reference spec:** `docs/superpowers/specs/2026-04-29-clawchat-tools-parity-design.md`.

---

## File map

| File | Phase | Action | Responsibility |
|---|---|---|---|
| `src/clawchat_gateway/tools.py` | A (Backend) | create | 6 async handler functions; error envelope helpers |
| `src/clawchat_gateway/profile.py` | A (Backend) | rewrite CLI; remove legacy `update_nickname` / `update_avatar` async helpers; keep `load_profile_config` + `_avatar_path` if reused | CLI mirroring tool surface |
| `__init__.py` | A (Backend) | re-wire `_register_tools` to the 6 new tools | Plugin registration |
| `tests/test_tools.py` | B (QA) | create | Handler-level coverage (13 cases) |
| `tests/test_profile.py` | B (QA) | rewrite | New CLI subcommand coverage |
| `README.md` | C (Docs) | refresh | Tool list, quickstart |
| `CLAUDE.md` | C (Docs) | refresh | Common commands, plugin-registration sentence |
| `dev_install.md` | C (Docs) | refresh | CLI references |
| `install.md` | C (Docs) | refresh | CLI references |
| `docs/architecture.md` | C (Docs) | refresh | Tool list |
| `docs/plugin-entrypoint.md` | C (Docs) | refresh | Handler table + tool list |
| `docs/profile.md` | C (Docs) | rewrite | New CLI subcommands |
| `docs/tests.md` | C (Docs) | refresh | New test descriptions |
| `skills/clawchat/SKILL.md` | — | **DO NOT TOUCH** | Out of scope this phase |
| `docs/skill.md` | — | **DO NOT TOUCH** | Out of scope this phase |

---

# Phase A — Backend implementation

**Branch from:** the worktree branch already created (`agent/planner/8fefe021`) — Backend-Dev should work on this branch (or a child branch off it) and push commits.

**Specialist:** `Backend-Dev`.

## Task A1: Create `tools.py` skeleton with shared helpers

**Files:**
- Create: `src/clawchat_gateway/tools.py`

- [ ] **Step 1: Write the file**

```python
"""Hermes tool handlers for ClawChat. Single source of truth for tool registration
and the `python -m clawchat_gateway.profile` CLI."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

from clawchat_gateway.api_client import ClawChatApiClient, ClawChatApiError
from clawchat_gateway.profile import ProfileConfigError, load_profile_config

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _config_error(message: str) -> dict[str, Any]:
    return {"error": "config", "message": message}


def _validation_error(message: str) -> dict[str, Any]:
    return {"error": "validation", "message": message}


def _api_error(err: ClawChatApiError) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if err.status is not None:
        meta["status"] = err.status
    if err.path is not None:
        meta["path"] = err.path
    if err.code is not None:
        meta["code"] = err.code
    out: dict[str, Any] = {"error": err.kind, "message": err.message}
    if meta:
        out["meta"] = meta
    return out


def _unknown_error(exc: BaseException) -> dict[str, Any]:
    return {"error": "unknown", "message": str(exc)}


def _build_client() -> tuple[ClawChatApiClient | None, dict[str, Any] | None]:
    try:
        config = load_profile_config()
    except ProfileConfigError as exc:
        return None, _config_error(str(exc))
    return (
        ClawChatApiClient(
            base_url=config.base_url,
            token=config.token,
            user_id=config.user_id,
        ),
        None,
    )


def _validate_upload_path(file_path: str) -> tuple[Path | None, dict[str, Any] | None]:
    if not isinstance(file_path, str) or not file_path:
        return None, _validation_error("filePath is required")
    path = Path(file_path)
    if not path.is_absolute():
        return None, _validation_error(f"filePath must be an absolute local path (got {file_path!r})")
    if not path.exists():
        return None, _validation_error(f"file does not exist: {path}")
    if not path.is_file():
        return None, _validation_error(f"not a regular file: {path}")
    size = path.stat().st_size
    if size <= 0:
        return None, _validation_error(f"file is empty: {path}")
    if size > MAX_UPLOAD_BYTES:
        return None, _validation_error(
            f"file too large ({size} bytes; max {MAX_UPLOAD_BYTES})"
        )
    return path, None


def _infer_mime(path: Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"
```

- [ ] **Step 2: Commit**

```bash
git add src/clawchat_gateway/tools.py
git commit -m "feat(tools): add tools.py skeleton with envelope/validation helpers"
```

## Task A2: Implement `get_account_profile` and `get_user_profile`

**Files:**
- Modify: `src/clawchat_gateway/tools.py` (append)

- [ ] **Step 1: Append to `tools.py`**

```python
async def get_account_profile() -> dict[str, Any]:
    client, err = _build_client()
    if err is not None:
        return err
    try:
        return await client.get_my_profile()
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


async def get_user_profile(user_id: str) -> dict[str, Any]:
    if not isinstance(user_id, str) or not user_id.strip():
        return _validation_error("userId is required")
    client, err = _build_client()
    if err is not None:
        return err
    try:
        return await client.get_user_info(user_id.strip())
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)
```

- [ ] **Step 2: Commit**

```bash
git add src/clawchat_gateway/tools.py
git commit -m "feat(tools): add get_account_profile and get_user_profile handlers"
```

## Task A3: Implement `list_account_friends`

**Files:**
- Modify: `src/clawchat_gateway/tools.py` (append)

- [ ] **Step 1: Append to `tools.py`**

```python
async def list_account_friends(
    page: int | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    page_value = 1 if page is None else page
    size_value = 20 if page_size is None else page_size
    if not isinstance(page_value, int) or page_value < 1:
        return _validation_error(f"page must be an integer >= 1 (got {page!r})")
    if not isinstance(size_value, int) or not (1 <= size_value <= 100):
        return _validation_error(f"pageSize must be an integer in 1..100 (got {page_size!r})")

    client, err = _build_client()
    if err is not None:
        return err
    try:
        return await client.list_friends(page=page_value, page_size=size_value)
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)
```

- [ ] **Step 2: Commit**

```bash
git add src/clawchat_gateway/tools.py
git commit -m "feat(tools): add list_account_friends handler with default pagination"
```

## Task A4: Implement `update_account_profile`

**Files:**
- Modify: `src/clawchat_gateway/tools.py` (append)

- [ ] **Step 1: Append to `tools.py`**

```python
async def update_account_profile(
    nickname: str | None = None,
    avatar_url: str | None = None,
    bio: str | None = None,
) -> dict[str, Any]:
    patch: dict[str, str] = {}
    if isinstance(nickname, str):
        patch["nickname"] = nickname
    if isinstance(avatar_url, str):
        patch["avatar_url"] = avatar_url
    if isinstance(bio, str):
        patch["bio"] = bio
    if not patch:
        return _validation_error(
            "at least one of nickname / avatar_url / bio is required"
        )

    client, err = _build_client()
    if err is not None:
        return err
    try:
        return await client.update_my_profile(**patch)
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)
```

- [ ] **Step 2: Commit**

```bash
git add src/clawchat_gateway/tools.py
git commit -m "feat(tools): add update_account_profile handler (nickname/avatar_url/bio)"
```

## Task A5: Implement `upload_avatar_image` and `upload_media_file`

**Files:**
- Modify: `src/clawchat_gateway/tools.py` (append)

- [ ] **Step 1: Append to `tools.py`**

```python
async def upload_avatar_image(file_path: str) -> dict[str, Any]:
    path, err = _validate_upload_path(file_path)
    if err is not None:
        return err
    client, cerr = _build_client()
    if cerr is not None:
        return cerr
    try:
        result = await client.upload_avatar(
            buffer=path.read_bytes(),
            filename=path.name,
            mime=_infer_mime(path),
        )
        return {"url": result.url, "size": result.size, "mime": result.mime}
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


async def upload_media_file(file_path: str) -> dict[str, Any]:
    path, err = _validate_upload_path(file_path)
    if err is not None:
        return err
    client, cerr = _build_client()
    if cerr is not None:
        return cerr
    try:
        result = await client.upload_media(
            buffer=path.read_bytes(),
            filename=path.name,
            mime=_infer_mime(path),
        )
        return {"url": result.url, "size": result.size, "mime": result.mime}
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)
```

Note: validation runs **before** building the client so an oversized/missing file fails locally without ever touching `load_profile_config()` or hitting the network.

- [ ] **Step 2: Commit**

```bash
git add src/clawchat_gateway/tools.py
git commit -m "feat(tools): add upload_avatar_image and upload_media_file (upload-only)"
```

## Task A6: Smoke import check

- [ ] **Step 1: Verify the module imports cleanly**

```bash
cd /path/to/hermes-clawchat
python -c "from clawchat_gateway import tools; print(sorted(n for n in dir(tools) if not n.startswith('_')))"
```

Expected output (order may vary):
```
['ClawChatApiClient', 'ClawChatApiError', 'MAX_UPLOAD_BYTES', 'ProfileConfigError', 'get_account_profile', 'get_user_profile', 'list_account_friends', 'load_profile_config', 'mimetypes', 'os', 'update_account_profile', 'upload_avatar_image', 'upload_media_file']
```

If any name is missing, fix and re-run before proceeding.

## Task A7: Rewire `__init__.py` — drop legacy tools

**Files:**
- Modify: `__init__.py:135-167, 204-253`

- [ ] **Step 1: Delete `_handle_clawchat_update_nickname` and `_handle_clawchat_update_avatar`**

Remove the two functions (lines ~135–166 currently) entirely.

- [ ] **Step 2: Delete the two `register_tool` calls + their schemas inside `_register_tools`**

Remove the `nickname_schema` block, the `ctx.register_tool("clawchat_update_nickname", ...)` call, the `avatar_schema` block, and the `ctx.register_tool("clawchat_update_avatar", ...)` call (currently lines ~204–253).

- [ ] **Step 3: Commit**

```bash
git add __init__.py
git commit -m "refactor(plugin): drop legacy update_nickname/update_avatar tool wiring"
```

## Task A8: Rewire `__init__.py` — register the 6 new tools

**Files:**
- Modify: `__init__.py` (add 6 handlers + 6 `ctx.register_tool` calls inside `_register_tools`)

- [ ] **Step 1: Add 6 handler functions just below `_handle_clawchat_activate`**

Each handler follows the existing pattern: log `task_id`, delegate to `clawchat_gateway.tools`, return result. Handlers DO NOT wrap errors with `_tool_error` — the new tools already return error dicts. Keep `_tool_error` for `clawchat_activate` only.

```python
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


async def _handle_clawchat_list_account_friends(args, **kw):
    task_id = kw.get("task_id") or "default"
    logger.info("clawchat_list_account_friends start task_id=%s", task_id)
    from clawchat_gateway import tools

    page = args.get("page")
    page_size = args.get("pageSize")
    result = await tools.list_account_friends(
        page=int(page) if isinstance(page, (int, str)) and str(page).strip() else None,
        page_size=int(page_size) if isinstance(page_size, (int, str)) and str(page_size).strip() else None,
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
```

- [ ] **Step 2: Inside `_register_tools(ctx)`, after the `clawchat_activate` `register_tool` call, add 6 new registrations**

Use trigger-rich descriptions adapted from openclaw's `src/tools.ts` `description` strings (preserve both English and Chinese trigger phrases). For each registration, supply the JSON-Schema dict in this shape:

```python
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
                "userId": {"type": "string", "description": "ClawChat user id (required, must be explicit)"},
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
            "At least one of the three must be present."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nickname": {"type": "string"},
                "avatar_url": {"type": "string"},
                "bio": {"type": "string"},
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
                "filePath": {"type": "string", "description": "Absolute local file path"},
            },
            "required": ["filePath"],
        },
    },
    _handle_clawchat_upload_media_file,
    is_async=True,
    description="Upload ClawChat Media File",
    emoji="📎",
)
```

- [ ] **Step 3: Commit**

```bash
git add __init__.py
git commit -m "feat(plugin): register 6 new clawchat_* tools backed by tools.py handlers"
```

## Task A9: Rework `profile.py` CLI

**Files:**
- Rewrite: `src/clawchat_gateway/profile.py`

The new file keeps `ProfileConfig`, `ProfileConfigError`, `_hermes_home`, `_load_yaml`, `load_profile_config` (all still used by `tools.py` and other tests). It removes `update_nickname`, `update_avatar`, and `_avatar_path` (the upload-path validation now lives in `tools._validate_upload_path`). Its `main(argv)` exposes 6 subcommands.

- [ ] **Step 1: Replace the file with the following content**

```python
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from clawchat_gateway.api_client import DEFAULT_BASE_URL


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


def _emit(result: dict[str, Any]) -> int:
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if isinstance(result, dict) and "error" in result:
        print(text, file=sys.stderr)
        return 1
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m clawchat_gateway.profile")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("get", help="Get the configured ClawChat account profile")

    p_user = sub.add_parser("get-user", help="Get a ClawChat user's public profile by userId")
    p_user.add_argument("user_id")

    p_friends = sub.add_parser("friends", help="List the configured account's friends")
    p_friends.add_argument("--page", type=int, default=None)
    p_friends.add_argument("--page-size", type=int, default=None, dest="page_size")

    p_update = sub.add_parser("update", help="Update the configured account profile")
    p_update.add_argument("--nickname", default=None)
    p_update.add_argument("--avatar-url", default=None, dest="avatar_url")
    p_update.add_argument("--bio", default=None)

    p_avatar = sub.add_parser("upload-avatar", help="Upload a local image as a ClawChat avatar (returns URL only)")
    p_avatar.add_argument("path")

    p_media = sub.add_parser("upload-media", help="Upload a local file as ClawChat media (returns URL)")
    p_media.add_argument("path")

    args = parser.parse_args(argv)

    from clawchat_gateway import tools

    if args.command == "get":
        result = asyncio.run(tools.get_account_profile())
    elif args.command == "get-user":
        result = asyncio.run(tools.get_user_profile(args.user_id))
    elif args.command == "friends":
        result = asyncio.run(
            tools.list_account_friends(page=args.page, page_size=args.page_size)
        )
    elif args.command == "update":
        result = asyncio.run(
            tools.update_account_profile(
                nickname=args.nickname,
                avatar_url=args.avatar_url,
                bio=args.bio,
            )
        )
    elif args.command == "upload-avatar":
        result = asyncio.run(tools.upload_avatar_image(args.path))
    elif args.command == "upload-media":
        result = asyncio.run(tools.upload_media_file(args.path))
    else:
        parser.error(f"unknown command: {args.command}")
        return 2

    return _emit(result)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-check the CLI parser**

```bash
python -m clawchat_gateway.profile --help
python -m clawchat_gateway.profile update --help
```

Expected: argparse prints help with all 6 subcommands and `--nickname / --avatar-url / --bio` flags on `update`.

- [ ] **Step 3: Commit**

```bash
git add src/clawchat_gateway/profile.py
git commit -m "refactor(profile): rework CLI to 6 subcommands matching new tool surface"
```

## Task A10: Verify imports and skip broken existing tests temporarily

The existing `tests/test_profile.py` imports `update_nickname` and `update_avatar` which are now gone. QA will rewrite that file in Phase B; for Phase A you should sanity-check only:

- [ ] **Step 1: Confirm modules import**

```bash
python -c "from clawchat_gateway import tools, profile; print('ok')"
```
Expected: `ok`.

- [ ] **Step 2: Run subset of tests that should still pass**

```bash
pytest tests/test_api_client.py tests/test_activate.py tests/test_config.py tests/test_install.py -q
```
Expected: all green. (Don't run `tests/test_profile.py` yet — it will fail until Phase B rewrites it. That's OK.)

End of Phase A. Phase A is complete when `tools.py` exists with all 6 handlers, `__init__.py` registers the 7 tools, `profile.py` CLI works, and the unaffected test files still pass.

---

# Phase B — Tests

**Specialist:** `QA`. Depends on Phase A being merged (or at least pushed to the same branch).

## Task B1: Create `tests/test_tools.py` — fixtures

**Files:**
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write the file (fixture + helpers)**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from clawchat_gateway import tools
from clawchat_gateway.api_client import ClawChatApiClient, ClawChatApiError, UploadResult


@pytest.fixture
def hermes_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _write_config(home: Path, *, token: str = "tk", user_id: str = "u1", base_url: str = "http://api.example") -> None:
    extra: dict[str, Any] = {"base_url": base_url}
    if token:
        extra["token"] = token
    if user_id:
        extra["user_id"] = user_id
    (home / "config.yaml").write_text(
        yaml.safe_dump({"platforms": {"clawchat": {"extra": extra}}}),
        encoding="utf-8",
    )


@pytest.fixture
def configured(hermes_home):
    _write_config(hermes_home)
    return hermes_home


class _FakeClient:
    """Captures every method call on the real ClawChatApiClient surface."""

    def __init__(self, responses: dict[str, Any] | None = None, raises: BaseException | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._responses = responses or {}
        self._raises = raises

    async def get_my_profile(self):
        self.calls.append(("get_my_profile", {}))
        if self._raises:
            raise self._raises
        return self._responses.get("get_my_profile", {"id": "u1"})

    async def get_user_info(self, user_id):
        self.calls.append(("get_user_info", {"user_id": user_id}))
        if self._raises:
            raise self._raises
        return self._responses.get("get_user_info", {"id": user_id})

    async def list_friends(self, *, page, page_size):
        self.calls.append(("list_friends", {"page": page, "page_size": page_size}))
        if self._raises:
            raise self._raises
        return self._responses.get("list_friends", {"items": [], "page": page, "pageSize": page_size})

    async def update_my_profile(self, **patch):
        self.calls.append(("update_my_profile", dict(patch)))
        if self._raises:
            raise self._raises
        return self._responses.get("update_my_profile", {"id": "u1", **patch})

    async def upload_avatar(self, *, buffer, filename, mime):
        self.calls.append(("upload_avatar", {"filename": filename, "mime": mime, "size": len(buffer)}))
        if self._raises:
            raise self._raises
        return self._responses.get(
            "upload_avatar",
            UploadResult(url="https://cdn/avatar.png", size=len(buffer), mime=mime),
        )

    async def upload_media(self, *, buffer, filename, mime):
        self.calls.append(("upload_media", {"filename": filename, "mime": mime, "size": len(buffer)}))
        if self._raises:
            raise self._raises
        return self._responses.get(
            "upload_media",
            UploadResult(url="https://cdn/media.png", size=len(buffer), mime=mime),
        )


@pytest.fixture
def stub_client(monkeypatch):
    """Returns a holder that the test fills with a `_FakeClient`. Every
    `tools._build_client()` call returns (client, None)."""
    holder = {"client": _FakeClient()}

    def _build():
        return holder["client"], None

    monkeypatch.setattr(tools, "_build_client", _build)
    return holder
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_tools.py
git commit -m "test(tools): add fixtures and fake client"
```

## Task B2: Happy-path tests — all 6 handlers

- [ ] **Step 1: Append to `tests/test_tools.py`**

```python
async def test_get_account_profile_returns_data(stub_client):
    stub_client["client"]._responses["get_my_profile"] = {"id": "u1", "nickname": "Alice"}
    assert await tools.get_account_profile() == {"id": "u1", "nickname": "Alice"}
    assert stub_client["client"].calls == [("get_my_profile", {})]


async def test_get_user_profile_returns_data(stub_client):
    stub_client["client"]._responses["get_user_info"] = {"id": "u9", "nickname": "Bob"}
    assert await tools.get_user_profile("u9") == {"id": "u9", "nickname": "Bob"}
    assert stub_client["client"].calls == [("get_user_info", {"user_id": "u9"})]


async def test_list_account_friends_default_pagination(stub_client):
    await tools.list_account_friends()
    assert stub_client["client"].calls == [("list_friends", {"page": 1, "page_size": 20})]


async def test_list_account_friends_custom_pagination(stub_client):
    await tools.list_account_friends(page=3, page_size=50)
    assert stub_client["client"].calls == [("list_friends", {"page": 3, "page_size": 50})]


async def test_update_account_profile_partial(stub_client):
    result = await tools.update_account_profile(nickname="Hermes")
    assert result["nickname"] == "Hermes"
    assert stub_client["client"].calls == [("update_my_profile", {"nickname": "Hermes"})]


async def test_update_account_profile_all_fields(stub_client):
    await tools.update_account_profile(nickname="N", avatar_url="https://x", bio="hi")
    assert stub_client["client"].calls == [
        ("update_my_profile", {"nickname": "N", "avatar_url": "https://x", "bio": "hi"}),
    ]


async def test_upload_avatar_image_happy(stub_client, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    result = await tools.upload_avatar_image(str(img))
    assert result == {"url": "https://cdn/avatar.png", "size": 8, "mime": "image/png"}
    assert stub_client["client"].calls[0][0] == "upload_avatar"


async def test_upload_media_file_happy(stub_client, tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    result = await tools.upload_media_file(str(f))
    assert result["url"] == "https://cdn/media.png"
    assert stub_client["client"].calls[0][0] == "upload_media"
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_tools.py
git commit -m "test(tools): cover happy paths for all 6 handlers"
```

## Task B3: Config-error tests

- [ ] **Step 1: Append to `tests/test_tools.py`**

```python
async def test_get_account_profile_no_config(hermes_home):
    # No config.yaml at all
    result = await tools.get_account_profile()
    assert result["error"] == "config"


async def test_get_account_profile_missing_token(hermes_home):
    _write_config(hermes_home, token="")
    result = await tools.get_account_profile()
    assert result["error"] == "config"
    assert "token" in result["message"]


async def test_get_account_profile_missing_user_id(hermes_home):
    _write_config(hermes_home, user_id="")
    result = await tools.get_account_profile()
    assert result["error"] == "config"
    assert "user_id" in result["message"]
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_tools.py
git commit -m "test(tools): cover config error paths"
```

## Task B4: Validation-error tests

- [ ] **Step 1: Append to `tests/test_tools.py`**

```python
async def test_get_user_profile_empty_user_id(stub_client):
    result = await tools.get_user_profile("")
    assert result["error"] == "validation"
    assert stub_client["client"].calls == []


async def test_get_user_profile_whitespace_user_id(stub_client):
    result = await tools.get_user_profile("   ")
    assert result["error"] == "validation"
    assert stub_client["client"].calls == []


async def test_list_account_friends_invalid_page(stub_client):
    assert (await tools.list_account_friends(page=0))["error"] == "validation"
    assert stub_client["client"].calls == []


async def test_list_account_friends_invalid_page_size(stub_client):
    assert (await tools.list_account_friends(page_size=200))["error"] == "validation"
    assert (await tools.list_account_friends(page_size=0))["error"] == "validation"
    assert stub_client["client"].calls == []


async def test_update_account_profile_no_fields(stub_client):
    result = await tools.update_account_profile()
    assert result["error"] == "validation"
    assert stub_client["client"].calls == []


async def test_upload_avatar_relative_path(stub_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "rel.png").write_bytes(b"x")
    result = await tools.upload_avatar_image("rel.png")
    assert result["error"] == "validation"
    assert stub_client["client"].calls == []


async def test_upload_avatar_missing_file(stub_client, tmp_path):
    result = await tools.upload_avatar_image(str(tmp_path / "missing.png"))
    assert result["error"] == "validation"
    assert stub_client["client"].calls == []


async def test_upload_media_oversized_file(stub_client, tmp_path):
    big = tmp_path / "big.bin"
    big.write_bytes(b"\x00" * (tools.MAX_UPLOAD_BYTES + 1))
    result = await tools.upload_media_file(str(big))
    assert result["error"] == "validation"
    assert "too large" in result["message"]
    assert stub_client["client"].calls == []
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_tools.py
git commit -m "test(tools): cover validation errors (paths, sizes, missing args)"
```

## Task B5: Backend-error tests (auth / api / transport)

- [ ] **Step 1: Append to `tests/test_tools.py`**

```python
async def test_auth_error_maps_to_auth(stub_client):
    stub_client["client"] = _FakeClient(
        raises=ClawChatApiError(kind="auth", message="unauthorized", status=401, path="/v1/users/me")
    )
    result = await tools.get_account_profile()
    assert result["error"] == "auth"
    assert result["meta"]["status"] == 401
    assert result["meta"]["path"] == "/v1/users/me"


async def test_api_error_maps_to_api_with_code(stub_client):
    stub_client["client"] = _FakeClient(
        raises=ClawChatApiError(kind="api", message="bad request", status=200, path="/v1/users/me", code=42)
    )
    result = await tools.get_account_profile()
    assert result["error"] == "api"
    assert result["meta"]["code"] == 42


async def test_transport_error_maps_to_transport(stub_client):
    stub_client["client"] = _FakeClient(
        raises=ClawChatApiError(kind="transport", message="connection refused", path="/v1/users/me")
    )
    result = await tools.get_account_profile()
    assert result["error"] == "transport"
    assert result["meta"]["path"] == "/v1/users/me"


async def test_unknown_exception_maps_to_unknown(stub_client):
    stub_client["client"] = _FakeClient(raises=RuntimeError("boom"))
    result = await tools.get_account_profile()
    assert result["error"] == "unknown"
    assert result["message"] == "boom"
```

- [ ] **Step 2: Run all of `test_tools.py`**

```bash
pytest tests/test_tools.py -v
```
Expected: every test green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_tools.py
git commit -m "test(tools): cover api error mapping (auth/api/transport/unknown)"
```

## Task B6: Rewrite `tests/test_profile.py` for the new CLI

**Files:**
- Rewrite: `tests/test_profile.py`

- [ ] **Step 1: Replace the file with the following**

```python
from __future__ import annotations

import json

import pytest
import yaml

from clawchat_gateway.profile import ProfileConfigError, load_profile_config, main


def _write_config(home, *, token="tk", user_id="u1", base_url="http://127.0.0.1:1"):
    extra = {"base_url": base_url}
    if token:
        extra["token"] = token
    if user_id:
        extra["user_id"] = user_id
    (home / "config.yaml").write_text(
        yaml.safe_dump({"platforms": {"clawchat": {"extra": extra}}}),
        encoding="utf-8",
    )


def test_load_profile_config_requires_token(monkeypatch, tmp_path):
    _write_config(tmp_path, token="")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with pytest.raises(ProfileConfigError, match="token"):
        load_profile_config()


def test_load_profile_config_requires_user_id(monkeypatch, tmp_path):
    _write_config(tmp_path, user_id="")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with pytest.raises(ProfileConfigError, match="user_id"):
        load_profile_config()


def test_cli_get_calls_handler_and_emits_json(monkeypatch, tmp_path, capsys):
    _write_config(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    async def fake_get_account_profile():
        return {"id": "u1", "nickname": "Alice"}

    from clawchat_gateway import tools

    monkeypatch.setattr(tools, "get_account_profile", fake_get_account_profile)

    rc = main(["get"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"id": "u1", "nickname": "Alice"}


def test_cli_update_emits_validation_error_to_stderr(monkeypatch, tmp_path, capsys):
    _write_config(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    rc = main(["update"])  # no fields → validation error from tools.update_account_profile
    assert rc == 1
    captured = capsys.readouterr()
    err = json.loads(captured.err)
    assert err["error"] == "validation"
    assert captured.out == ""


def test_cli_upload_avatar_relative_path_emits_validation(monkeypatch, tmp_path, capsys):
    _write_config(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "rel.png").write_bytes(b"x")

    rc = main(["upload-avatar", "rel.png"])
    assert rc == 1
    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "validation"


def test_cli_friends_passes_pagination(monkeypatch, tmp_path, capsys):
    _write_config(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    seen = {}

    async def fake_list(page=None, page_size=None):
        seen["page"] = page
        seen["page_size"] = page_size
        return {"items": [], "page": page, "pageSize": page_size}

    from clawchat_gateway import tools

    monkeypatch.setattr(tools, "list_account_friends", fake_list)

    rc = main(["friends", "--page", "2", "--page-size", "50"])
    assert rc == 0
    assert seen == {"page": 2, "page_size": 50}
```

- [ ] **Step 2: Run it**

```bash
pytest tests/test_profile.py -v
```
Expected: all green.

- [ ] **Step 3: Run the full suite**

```bash
pytest -q
```
Expected: green. If any unrelated test fails, investigate and fix or escalate to the parent issue.

- [ ] **Step 4: Commit**

```bash
git add tests/test_profile.py
git commit -m "test(profile): rewrite around new CLI subcommands"
```

End of Phase B.

---

# Phase C — Documentation refresh

**Specialist:** `Tech-Writer`. Depends on Phase A merged. Can run in parallel with Phase B.

## Task C1: `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current file**

```bash
cat README.md
```

- [ ] **Step 2: Replace the tools/quickstart section**

Find any block listing the 3 old tools (`clawchat_activate`, `clawchat_update_nickname`, `clawchat_update_avatar`) and any quickstart referring to `python -m clawchat_gateway.profile nickname/avatar`. Replace with:

- The 7-tool list (`clawchat_activate` + 6 new) — one line each, name and one-line purpose.
- New quickstart commands:

  ```bash
  # Activate (one-time)
  python -m clawchat_gateway.activate <CODE>

  # Inspect / update
  python -m clawchat_gateway.profile get
  python -m clawchat_gateway.profile update --nickname "Bot" --bio "hi"
  python -m clawchat_gateway.profile upload-avatar /abs/path/to/image.png
  python -m clawchat_gateway.profile upload-media /abs/path/to/file.pdf
  python -m clawchat_gateway.profile friends --page 1 --page-size 20
  python -m clawchat_gateway.profile get-user <USER_ID>
  ```

Do not introduce any new tool names not listed above.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): refresh tool list and quickstart for new clawchat_* surface"
```

## Task C2: `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md:34-35` and `CLAUDE.md:44`

- [ ] **Step 1: Replace lines 34–35**

```
python -m clawchat_gateway.profile nickname "NEW_NAME"
python -m clawchat_gateway.profile avatar /absolute/path/to/image.png
```

with:

```
# Inspect / update profile (requires activation first)
python -m clawchat_gateway.profile get
python -m clawchat_gateway.profile get-user <USER_ID>
python -m clawchat_gateway.profile friends [--page N] [--page-size N]
python -m clawchat_gateway.profile update [--nickname X] [--avatar-url URL] [--bio X]
python -m clawchat_gateway.profile upload-avatar /absolute/path/to/image.png
python -m clawchat_gateway.profile upload-media /absolute/path/to/file
```

- [ ] **Step 2: Update line 44**

Find the sentence:

> "registers three Hermes tools (`clawchat_activate`, `clawchat_update_nickname`, `clawchat_update_avatar`)"

Replace with:

> "registers seven Hermes tools (`clawchat_activate`, `clawchat_get_account_profile`, `clawchat_get_user_profile`, `clawchat_list_account_friends`, `clawchat_update_account_profile`, `clawchat_upload_avatar_image`, `clawchat_upload_media_file`)"

- [ ] **Step 3: Update the `profile.py` description bullet**

Find the bullet:

> "**`profile.py`** — nickname/avatar updates. Avatar must be an absolute local path; the command always uploads via `/v1/files/upload-url` first, then PATCHes `/v1/users/me` with the returned URL."

Replace with:

> "**`profile.py`** — CLI subcommands (`get`, `get-user`, `friends`, `update`, `upload-avatar`, `upload-media`) that mirror the `clawchat_*` tool surface. Each subcommand calls the same handler in `tools.py` that the tool registration calls."

- [ ] **Step 4: Add a short bullet for `tools.py`**

Add immediately above the `profile.py` bullet:

> "**`tools.py`** — async tool handlers for the six new `clawchat_*` tools. Single source of truth shared by the Hermes tool registration in `__init__.py` and the CLI in `profile.py`. Returns result dicts; never raises."

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude.md): refresh tool list, common commands, profile/tools bullets"
```

## Task C3: `dev_install.md` and `install.md`

**Files:**
- Modify: `dev_install.md`, `install.md`

- [ ] **Step 1: Search and replace**

For each file, replace any occurrence of:
- `python -m clawchat_gateway.profile nickname …` → `python -m clawchat_gateway.profile update --nickname …`
- `python -m clawchat_gateway.profile avatar /path` → `python -m clawchat_gateway.profile upload-avatar /path` (and follow with a separate `update --avatar-url` invocation if the original example also expected the profile to be updated; otherwise just `upload-avatar`).

If either file contains a tool list, refresh it to the 7-tool list (the same one used in README).

- [ ] **Step 2: Commit**

```bash
git add dev_install.md install.md
git commit -m "docs(install): update CLI examples for new clawchat_gateway.profile subcommands"
```

## Task C4: `docs/architecture.md`, `docs/plugin-entrypoint.md`, `docs/profile.md`, `docs/tests.md`

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/plugin-entrypoint.md`
- Rewrite: `docs/profile.md`
- Modify: `docs/tests.md`

- [ ] **Step 1: `docs/architecture.md`**

Find the bulleted tool list (currently includes `clawchat_update_nickname`, `clawchat_update_avatar`) and replace with the 7-tool list (each name + one-line purpose).

- [ ] **Step 2: `docs/plugin-entrypoint.md`**

Replace the handler table (currently `_handle_clawchat_update_nickname` / `_handle_clawchat_update_avatar`) with rows for the 6 new handlers and `_handle_clawchat_activate`. Format:

| Handler | Args | Backing |
|---|---|---|
| `_handle_clawchat_activate` | `code`, optional `baseUrl` | `clawchat_gateway.activate.activate` |
| `_handle_clawchat_get_account_profile` | — | `clawchat_gateway.tools.get_account_profile` |
| `_handle_clawchat_get_user_profile` | `userId` | `clawchat_gateway.tools.get_user_profile` |
| `_handle_clawchat_list_account_friends` | optional `page`, optional `pageSize` | `clawchat_gateway.tools.list_account_friends` |
| `_handle_clawchat_update_account_profile` | optional `nickname`, optional `avatar_url`, optional `bio` (≥1) | `clawchat_gateway.tools.update_account_profile` |
| `_handle_clawchat_upload_avatar_image` | `filePath` | `clawchat_gateway.tools.upload_avatar_image` |
| `_handle_clawchat_upload_media_file` | `filePath` | `clawchat_gateway.tools.upload_media_file` |

Replace the "Registered tools" bullet list with the same 7 names (with emojis: 🔑 / 👤 / 🧑 / 👥 / ✏️ / 🖼️ / 📎).

- [ ] **Step 3: Rewrite `docs/profile.md`**

Replace its body with sections that document:
- `load_profile_config()` (still public).
- The 6 CLI subcommands of `python -m clawchat_gateway.profile`, each with one or two example invocations and what they print on success/error.
- The error envelope shape (referencing the design doc).

Do **not** mention `update_nickname` / `update_avatar`; those functions no longer exist.

- [ ] **Step 4: Update `docs/tests.md`**

Replace lines mentioning `update_nickname` / `update_avatar` with the new test files / cases:
- `tests/test_tools.py` — handler-level tests (config / validation / api errors / happy paths).
- `tests/test_profile.py` — CLI integration tests for the 6 subcommands.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture.md docs/plugin-entrypoint.md docs/profile.md docs/tests.md
git commit -m "docs: refresh architecture/plugin-entrypoint/profile/tests for new tool surface"
```

End of Phase C.

---

## Final verification (before parent issue moves to `in_review`)

Once Phases A, B, C are merged onto the same branch:

- [ ] Run the full suite:

  ```bash
  pytest -q
  ```
  Expected: all green.

- [ ] Smoke-test the CLI without an activated config (config missing):

  ```bash
  HERMES_HOME=/tmp/hermes-empty python -m clawchat_gateway.profile get
  ```
  Expected stderr: JSON with `"error": "config"`. Exit code 1.

- [ ] Grep for old names that should not exist:

  ```bash
  grep -RnE 'clawchat_update_nickname|clawchat_update_avatar' --include='*.py' --include='*.md' .
  ```
  Expected: only matches inside `skills/clawchat/SKILL.md` and `docs/skill.md` (out of scope this phase) and **possibly** in design/plan docs under `docs/superpowers/`. Any other match is a bug.

- [ ] Confirm SKILL.md was not touched:

  ```bash
  git diff --stat HEAD~N skills/clawchat/SKILL.md docs/skill.md
  ```
  (where `N` covers all phase commits) Expected: empty.
