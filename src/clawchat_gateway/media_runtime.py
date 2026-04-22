from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence


def infer_media_kind_from_mime(mime: str) -> str:
    normalized = mime.split(";", 1)[0].strip().lower()
    if normalized.startswith("image/"):
        return "image"
    if normalized.startswith("audio/"):
        return "audio"
    if normalized.startswith("video/"):
        return "video"
    return "file"


def ensure_allowed_local_path(path: str, allowed_roots: Sequence[str]) -> Path:
    resolved = Path(path).expanduser().resolve()
    roots = [Path(root).expanduser().resolve() for root in allowed_roots]
    if not roots:
        raise ValueError("no allowed roots configured")
    if not any(root == resolved or root in resolved.parents for root in roots):
        raise ValueError(f"path not under allowed roots: {resolved}")
    return resolved
