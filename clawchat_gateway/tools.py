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


def _positive_int(value: Any, field: str) -> tuple[int | None, dict[str, Any] | None]:
    if not isinstance(value, int) or value < 1:
        return None, _validation_error(f"{field} must be an integer >= 1")
    return value, None


async def search_users(q: str | None = None, limit: int | None = None) -> dict[str, Any]:
    if limit is not None and (not isinstance(limit, int) or not (1 <= limit <= 100)):
        return _validation_error("limit must be an integer in 1..100")

    client, err = _build_client()
    if err is not None:
        return err
    try:
        return await client.search_users(q=q or "", limit=limit)
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


async def list_moments(before: int | None = None, limit: int | None = None) -> dict[str, Any]:
    if before is not None and (not isinstance(before, int) or before < 1):
        return _validation_error("before must be an integer >= 1")
    if limit is not None and (not isinstance(limit, int) or not (1 <= limit <= 100)):
        return _validation_error("limit must be an integer in 1..100")

    client, err = _build_client()
    if err is not None:
        return err
    try:
        return await client.list_moments(before=before, limit=limit)
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


async def create_moment(
    text: str | None = None,
    images: list[str] | None = None,
) -> dict[str, Any]:
    if text is not None and not isinstance(text, str):
        return _validation_error("text must be a string")
    if images is not None and (
        not isinstance(images, list) or any(not isinstance(item, str) for item in images)
    ):
        return _validation_error("images must be a list of image URLs")
    if not text and not images:
        return _validation_error("at least one of text or images is required")

    client, err = _build_client()
    if err is not None:
        return err
    try:
        return await client.create_moment(text=text, images=images)
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


async def delete_moment(moment_id: int) -> dict[str, Any]:
    moment_id_value, err = _positive_int(moment_id, "momentId")
    if err is not None:
        return err

    client, cerr = _build_client()
    if cerr is not None:
        return cerr
    try:
        return await client.delete_moment(moment_id_value)
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


async def toggle_moment_reaction(moment_id: int, emoji: str) -> dict[str, Any]:
    moment_id_value, err = _positive_int(moment_id, "momentId")
    if err is not None:
        return err
    if not isinstance(emoji, str) or not emoji.strip():
        return _validation_error("emoji is required")

    client, cerr = _build_client()
    if cerr is not None:
        return cerr
    try:
        return await client.toggle_moment_reaction(moment_id=moment_id_value, emoji=emoji)
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


async def create_moment_comment(moment_id: int, text: str) -> dict[str, Any]:
    moment_id_value, err = _positive_int(moment_id, "momentId")
    if err is not None:
        return err
    if not isinstance(text, str) or not text.strip():
        return _validation_error("text is required")

    client, cerr = _build_client()
    if cerr is not None:
        return cerr
    try:
        return await client.create_moment_comment(moment_id=moment_id_value, text=text)
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


async def reply_moment_comment(
    moment_id: int,
    reply_to_comment_id: int,
    text: str,
) -> dict[str, Any]:
    moment_id_value, err = _positive_int(moment_id, "momentId")
    if err is not None:
        return err
    reply_to_comment_id_value, rerr = _positive_int(reply_to_comment_id, "replyToCommentId")
    if rerr is not None:
        return rerr
    if not isinstance(text, str) or not text.strip():
        return _validation_error("text is required")

    client, cerr = _build_client()
    if cerr is not None:
        return cerr
    try:
        return await client.reply_moment_comment(
            moment_id=moment_id_value,
            reply_to_comment_id=reply_to_comment_id_value,
            text=text,
        )
    except ClawChatApiError as exc:
        return _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _unknown_error(exc)


async def delete_moment_comment(moment_id: int, comment_id: int) -> dict[str, Any]:
    moment_id_value, err = _positive_int(moment_id, "momentId")
    if err is not None:
        return err
    comment_id_value, cerr = _positive_int(comment_id, "commentId")
    if cerr is not None:
        return cerr

    client, berr = _build_client()
    if berr is not None:
        return berr
    try:
        return await client.delete_moment_comment(
            moment_id=moment_id_value,
            comment_id=comment_id_value,
        )
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
