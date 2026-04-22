from pathlib import Path

import pytest

from clawchat_gateway.media_runtime import ensure_allowed_local_path, infer_media_kind_from_mime


def test_infer_media_kind_from_mime():
    assert infer_media_kind_from_mime("image/png") == "image"
    assert infer_media_kind_from_mime("audio/mpeg") == "audio"
    assert infer_media_kind_from_mime("video/mp4") == "video"
    assert infer_media_kind_from_mime("application/pdf") == "file"


def test_infer_media_kind_from_mime_handles_parameters_and_casing():
    assert infer_media_kind_from_mime("Image/PNG") == "image"
    assert infer_media_kind_from_mime("image/png; charset=binary") == "image"


def test_local_path_must_be_under_allowed_roots(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "a.txt"
    inside.write_text("x")
    assert ensure_allowed_local_path(str(inside), [str(allowed)]) == inside
    with pytest.raises(ValueError):
        ensure_allowed_local_path("/tmp/outside.txt", [str(allowed)])


def test_local_path_allows_nested_paths_under_allowed_root(tmp_path: Path):
    allowed = tmp_path / "allowed"
    nested = allowed / "nested" / "deeper"
    nested.mkdir(parents=True)
    inside = nested / "a.txt"
    inside.write_text("x")

    assert ensure_allowed_local_path(str(inside), [str(allowed)]) == inside


def test_local_path_fails_closed_without_allowed_roots(tmp_path: Path):
    inside = tmp_path / "a.txt"
    inside.write_text("x")

    with pytest.raises(ValueError):
        ensure_allowed_local_path(str(inside), [])
