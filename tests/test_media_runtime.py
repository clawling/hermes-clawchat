from pathlib import Path

import pytest

from clawchat_gateway.media_runtime import (
    DownloadedMedia,
    UploadMediaResult,
    derive_base_url,
    download_inbound_media,
    ensure_allowed_local_path,
    infer_media_kind_from_mime,
    upload_outbound_media,
)


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


def test_local_path_allows_existing_path_without_configured_allowed_roots(tmp_path: Path):
    inside = tmp_path / "a.txt"
    inside.write_text("x")

    assert ensure_allowed_local_path(str(inside), []) == inside


def test_derive_base_url_prefers_websocket_origin_for_media_gateway():
    assert (
        derive_base_url(
            websocket_url="ws://media.example.com/ws",
            base_url="https://api.example.com",
        )
        == "http://media.example.com"
    )


def test_derive_base_url_falls_back_to_websocket_origin():
    assert (
        derive_base_url(
            websocket_url="wss://chat.example.com/v2/client",
            base_url="",
        )
        == "https://chat.example.com"
    )
    assert (
        derive_base_url(
            websocket_url="ws://127.0.0.1:8080/v2/client",
            base_url="",
        )
        == "http://127.0.0.1:8080"
    )


@pytest.mark.asyncio
async def test_upload_outbound_media_uploads_local_path(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    image_path = allowed / "avatar.png"
    image_path.write_bytes(b"png-bytes")

    calls = []

    async def fake_upload(*, base_url: str, token: str, buffer: bytes, filename: str, mime: str):
        calls.append(
            {
                "base_url": base_url,
                "token": token,
                "buffer": buffer,
                "filename": filename,
                "mime": mime,
            }
        )
        return UploadMediaResult(
            url="https://cdn.example.com/avatar.png",
            mime="image/png",
            size=len(buffer),
        )

    fragments = await upload_outbound_media(
        [str(image_path)],
        base_url="https://api.example.com",
        websocket_url="",
        token="tk",
        media_local_roots=[str(allowed)],
        upload_file=fake_upload,
    )

    assert calls == [
        {
            "base_url": "https://api.example.com",
            "token": "tk",
            "buffer": b"png-bytes",
            "filename": "avatar.png",
            "mime": "image/png",
        }
    ]
    assert fragments == [
        {
            "kind": "image",
            "url": "https://cdn.example.com/avatar.png",
            "mime": "image/png",
            "size": len(b"png-bytes"),
            "name": "avatar.png",
        }
    ]


@pytest.mark.asyncio
async def test_upload_outbound_media_uploads_local_path_without_media_roots(
    tmp_path: Path,
):
    image_path = tmp_path / "generated.png"
    image_path.write_bytes(b"png-bytes")

    async def fake_upload(*, base_url: str, token: str, buffer: bytes, filename: str, mime: str):
        return UploadMediaResult(
            url="https://cdn.example.com/generated.png",
            mime=mime,
            size=len(buffer),
        )

    fragments = await upload_outbound_media(
        [str(image_path)],
        base_url="https://api.example.com",
        websocket_url="",
        token="tk",
        media_local_roots=[],
        upload_file=fake_upload,
    )

    assert fragments == [
        {
            "kind": "image",
            "url": "https://cdn.example.com/generated.png",
            "mime": "image/png",
            "size": len(b"png-bytes"),
            "name": "generated.png",
        }
    ]


@pytest.mark.asyncio
async def test_upload_outbound_media_skips_single_failed_item(monkeypatch, tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    image_path = allowed / "avatar.png"
    image_path.write_bytes(b"png-bytes")

    calls = []

    async def fake_upload(*, base_url: str, token: str, buffer: bytes, filename: str, mime: str):
        calls.append(filename)
        if filename == "avatar.png":
            raise RuntimeError("boom")
        return UploadMediaResult(
            url="https://cdn.example.com/other.png",
            mime="image/png",
            size=len(buffer),
        )

    monkeypatch.setattr(
        "clawchat_gateway.media_runtime._load_remote_media",
        lambda url: type("Loaded", (), {
            "buffer": b"remote-bytes",
            "filename": "other.png",
            "mime": "image/png",
        })(),
    )

    fragments = await upload_outbound_media(
        [str(image_path), "https://example.com/other.png"],
        base_url="https://api.example.com",
        websocket_url="",
        token="tk",
        media_local_roots=[str(allowed)],
        upload_file=fake_upload,
    )

    assert calls == ["avatar.png", "other.png"]
    assert fragments == [
        {
            "kind": "image",
            "url": "https://cdn.example.com/other.png",
            "mime": "image/png",
            "size": len(b"remote-bytes"),
            "name": "other.png",
        }
    ]


@pytest.mark.asyncio
async def test_upload_outbound_media_uses_uploaded_media_url_when_refetch_fails(monkeypatch):
    def fail_fetch(url: str):
        raise OSError("blocked")

    monkeypatch.setattr(
        "clawchat_gateway.media_runtime._load_remote_media",
        fail_fetch,
    )

    fragments = await upload_outbound_media(
        ["https://clawchat.example.com/media/reply.png"],
        base_url="https://api.example.com",
        websocket_url="",
        token="tk",
        media_local_roots=[],
    )

    assert fragments == [
        {
            "kind": "image",
            "url": "https://clawchat.example.com/media/reply.png",
            "mime": "image/png",
            "size": 0,
            "name": "reply.png",
        }
    ]


@pytest.mark.asyncio
async def test_download_inbound_media_resolves_relative_url_and_writes_local_file(
    monkeypatch, tmp_path: Path
):
    calls = []

    def fake_fetch(url: str, *, token: str):
        calls.append({"url": url, "token": token})
        return DownloadedMedia(
            local_path=tmp_path / "unused",
            mime="image/png",
            size=0,
            source_url=url,
        )

    def fake_write(*, url: str, token: str, download_dir: Path):
        fetched = fake_fetch(url, token=token)
        path = download_dir / "img.png"
        path.write_bytes(b"png-bytes")
        return DownloadedMedia(
            local_path=path,
            mime=fetched.mime,
            size=len(b"png-bytes"),
            source_url=fetched.source_url,
        )

    monkeypatch.setattr(
        "clawchat_gateway.media_runtime._download_inbound_media_sync",
        fake_write,
    )

    downloaded = await download_inbound_media(
        ["/media/files/img.png"],
        base_url="http://company.newbaselab.com:10086",
        websocket_url="ws://company.newbaselab.com:10086/ws",
        token="tk",
        download_dir=tmp_path,
    )

    assert calls == [
        {
            "url": "http://company.newbaselab.com:10086/media/files/img.png",
            "token": "tk",
        }
    ]
    assert downloaded == [
        DownloadedMedia(
            local_path=tmp_path / "img.png",
            mime="image/png",
            size=len(b"png-bytes"),
            source_url="http://company.newbaselab.com:10086/media/files/img.png",
        )
    ]
