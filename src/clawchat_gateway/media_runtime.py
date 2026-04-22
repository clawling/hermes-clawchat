from __future__ import annotations

from pathlib import Path


def infer_media_kind_from_mime(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "file"


def ensure_allowed_local_path(path: str, allowed_roots: list[str]) -> Path:
    resolved = Path(path).expanduser().resolve()
    roots = [Path(root).expanduser().resolve() for root in allowed_roots]
    if roots and not any(root == resolved or root in resolved.parents for root in roots):
        raise ValueError(f"path not under allowed roots: {resolved}")
    return resolved
