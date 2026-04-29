from __future__ import annotations

import pytest
import yaml

from clawchat_gateway import tools
from clawchat_gateway.api_client import ClawChatApiError, UploadResult


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


@pytest.fixture
def hermes_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


class _FakeClient:
    def __init__(self, *, raises=None, responses=None):
        self.calls = []
        self._raises = raises
        self._responses = responses or {}

    async def get_my_profile(self):
        self.calls.append(("get_my_profile", {}))
        if self._raises:
            raise self._raises
        return self._responses.get("get_my_profile", {"id": "u1", "nickname": "Alice"})

    async def get_user_info(self, user_id):
        self.calls.append(("get_user_info", {"user_id": user_id}))
        if self._raises:
            raise self._raises
        return self._responses.get("get_user_info", {"id": user_id, "nickname": "Bob"})

    async def list_friends(self, *, page=1, page_size=20):
        self.calls.append(("list_friends", {"page": page, "page_size": page_size}))
        if self._raises:
            raise self._raises
        return self._responses.get("list_friends", {"items": [], "page": page, "pageSize": page_size})

    async def update_my_profile(self, **patch):
        self.calls.append(("update_my_profile", patch))
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
    holder = {"client": _FakeClient()}

    def _build():
        return holder["client"], None

    monkeypatch.setattr(tools, "_build_client", _build)
    return holder


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
    file_path = tmp_path / "doc.pdf"
    file_path.write_bytes(b"%PDF-1.4\n")
    result = await tools.upload_media_file(str(file_path))
    assert result["url"] == "https://cdn/media.png"
    assert stub_client["client"].calls[0][0] == "upload_media"


async def test_get_account_profile_no_config(hermes_home):
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
