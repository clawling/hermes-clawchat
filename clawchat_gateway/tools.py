"""Hermes tool handlers for ClawChat.

This module is the single source of truth for the new profile/media tool
surface used by both Hermes tool registration and the profile CLI.
"""

from __future__ import annotations

import mimetypes
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
        return None, _validation_error(f"file too large ({size} bytes; max {MAX_UPLOAD_BYTES})")
    return path, None


def _infer_mime(path: Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


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
        return _validation_error("at least one of nickname / avatar_url / bio is required")

    client, err = _build_client()
    if err is not None:
        return err
    try:
        return await client.update_my_profile(**patch)
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


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
