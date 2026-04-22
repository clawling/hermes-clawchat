from pathlib import Path

import pytest

from clawchat_gateway.media_runtime import ensure_allowed_local_path, infer_media_kind_from_mime


def test_infer_media_kind_from_mime():
    assert infer_media_kind_from_mime("image/png") == "image"
    assert infer_media_kind_from_mime("audio/mpeg") == "audio"
    assert infer_media_kind_from_mime("video/mp4") == "video"
    assert infer_media_kind_from_mime("application/pdf") == "file"


def test_local_path_must_be_under_allowed_roots(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "a.txt"
    inside.write_text("x")
    assert ensure_allowed_local_path(str(inside), [str(allowed)]) == inside
    with pytest.raises(ValueError):
        ensure_allowed_local_path("/tmp/outside.txt", [str(allowed)])
