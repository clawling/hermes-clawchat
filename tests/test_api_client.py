from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from clawchat_gateway.api_client import (
    AGENTS_CONNECT_PLATFORM,
    AGENTS_CONNECT_TYPE,
    ClawChatApiClient,
    ClawChatApiError,
)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.paths.append(self.path)
        if self.path == "/v1/users/me":
            self._reply({"code": 0, "message": "ok", "data": {"id": "u1"}})
            return
        if self.path == "/v1/users/search?q=alice&limit=20":
            self._reply({"code": 0, "message": "ok", "data": {"users": [{"id": "u1"}]}})
            return
        if self.path == "/v1/moments?before=123&limit=30":
            self._reply({"code": 0, "message": "ok", "data": {"moments": [{"id": 122}]}})
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.last_path = self.path
        self.server.paths.append(self.path)
        if self.path == "/v1/moments":
            self.server.captured = json.loads(body.decode("utf-8"))
            self._reply({"code": 0, "message": "ok", "data": {"moment": {"id": 1}}})
            return
        if self.path == "/v1/moments/123/reactions":
            self.server.captured = json.loads(body.decode("utf-8"))
            self._reply(
                {
                    "code": 0,
                    "message": "ok",
                    "data": {"reactions": [{"emoji": self.server.captured["emoji"], "count": 1, "mine": True}]},
                }
            )
            return
        if self.path == "/v1/moments/123/comments":
            self.server.captured = json.loads(body.decode("utf-8"))
            self._reply({"code": 0, "message": "ok", "data": {"comment": {"id": 456}}})
            return
        if self.path == "/v1/agents/connect":
            payload = json.loads(body.decode("utf-8"))
            self.server.captured = payload
            self._reply(
                {
                    "code": 0,
                    "message": "ok",
                    "data": {
                        "access_token": "tk",
                        "refresh_token": "rt",
                        "agent": {"user_id": "agent-1"},
                    },
                }
            )
            return
        if self.path == "/media/upload":
            self.server.auth = self.headers.get("Authorization")
            self.server.content_type = self.headers.get("Content-Type")
            self._reply(
                {
                    "code": 0,
                    "message": "ok",
                    "data": {"url": "https://cdn/x.png", "size": 12, "mime": "image/png"},
                }
            )
            return
        if self.path == "/v1/files/upload-url":
            self.server.auth = self.headers.get("Authorization")
            self.server.content_type = self.headers.get("Content-Type")
            self._reply(
                {
                    "code": 0,
                    "message": "ok",
                    "data": {"url": "https://cdn/avatar.png", "size": 12, "mime": "image/png"},
                }
            )
            return
        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        self.server.last_path = self.path
        self.server.paths.append(self.path)
        if self.path in {"/v1/moments/123", "/v1/moments/123/comments/456"}:
            self._reply({"code": 0, "message": "ok", "data": {"ok": True}})
            return
        self.send_response(404)
        self.end_headers()

    def do_PATCH(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.last_path = self.path
        self.server.paths.append(self.path)
        self.server.auth = self.headers.get("Authorization")
        self.server.captured = json.loads(body.decode("utf-8"))
        if self.path == "/v1/users/me":
            self._reply({"code": 0, "message": "ok", "data": {"id": "u1", **self.server.captured}})
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return

    def _reply(self, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def api_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.paths = []
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()


@pytest.mark.asyncio
async def test_agents_connect_posts_fixed_body(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="")

    result = await client.agents_connect(code="INV-123")

    assert api_server.captured == {
        "code": "INV-123",
        "platform": AGENTS_CONNECT_PLATFORM,
        "type": AGENTS_CONNECT_TYPE,
    }
    assert result["access_token"] == "tk"
    assert result["agent"]["user_id"] == "agent-1"


@pytest.mark.asyncio
async def test_agents_connect_includes_tools_when_provided(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="")

    await client.agents_connect(code="INV-123", tools=["clawchat_get_my_profile", "clawchat_list_friends"])

    assert api_server.captured == {
        "code": "INV-123",
        "platform": AGENTS_CONNECT_PLATFORM,
        "type": AGENTS_CONNECT_TYPE,
        "tools": ["clawchat_get_my_profile", "clawchat_list_friends"],
    }


@pytest.mark.asyncio
async def test_upload_media_posts_multipart_with_bearer(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    result = await client.upload_media(buffer=b"hello", filename="x.png", mime="image/png")

    assert result.url == "https://cdn/x.png"
    assert api_server.last_path == "/media/upload"
    assert api_server.auth == "Bearer token-bob"
    assert "multipart/form-data" in api_server.content_type


@pytest.mark.asyncio
async def test_upload_avatar_uses_avatar_endpoint(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    result = await client.upload_avatar(buffer=b"hello", filename="avatar.png", mime="image/png")

    assert result.url == "https://cdn/avatar.png"
    assert api_server.last_path == "/v1/files/upload-url"
    assert api_server.auth == "Bearer token-bob"
    assert "multipart/form-data" in api_server.content_type


@pytest.mark.asyncio
async def test_update_my_profile_patches_current_user(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    result = await client.update_my_profile(nickname="Hermes", avatar_url="https://cdn/avatar.png")

    assert result["nickname"] == "Hermes"
    assert result["avatar_url"] == "https://cdn/avatar.png"
    assert api_server.last_path == "/v1/users/me"
    assert api_server.auth == "Bearer token-bob"
    assert api_server.captured == {
        "nickname": "Hermes",
        "avatar_url": "https://cdn/avatar.png",
    }


@pytest.mark.asyncio
async def test_search_users_sends_query(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    result = await client.search_users(q="alice", limit=20)

    assert result == {"users": [{"id": "u1"}]}
    assert api_server.paths[-1] == "/v1/users/search?q=alice&limit=20"


@pytest.mark.asyncio
async def test_list_moments_sends_query(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    result = await client.list_moments(before=123, limit=30)

    assert result == {"moments": [{"id": 122}]}
    assert api_server.paths[-1] == "/v1/moments?before=123&limit=30"


@pytest.mark.asyncio
async def test_create_moment_posts_json(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    await client.create_moment(text="hello", images=["https://cdn/a.png"])

    assert api_server.last_path == "/v1/moments"
    assert api_server.captured == {"text": "hello", "images": ["https://cdn/a.png"]}


@pytest.mark.asyncio
async def test_delete_moment_uses_moment_id(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    result = await client.delete_moment(123)

    assert result == {"ok": True}
    assert api_server.last_path == "/v1/moments/123"


@pytest.mark.asyncio
async def test_toggle_moment_reaction_posts_emoji(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    result = await client.toggle_moment_reaction(moment_id=123, emoji="👍")

    assert result["reactions"][0]["mine"] is True
    assert api_server.last_path == "/v1/moments/123/reactions"
    assert api_server.captured == {"emoji": "👍"}


@pytest.mark.asyncio
async def test_create_and_reply_moment_comment_post_expected_bodies(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    await client.create_moment_comment(moment_id=123, text="nice")
    assert api_server.captured == {"text": "nice"}

    await client.reply_moment_comment(moment_id=123, reply_to_comment_id=456, text="yes")
    assert api_server.captured == {"text": "yes", "reply_to_comment_id": 456}


@pytest.mark.asyncio
async def test_delete_moment_comment_uses_moment_and_comment_ids(api_server):
    client = ClawChatApiClient(base_url=f"http://127.0.0.1:{api_server.server_port}", token="token-bob")

    result = await client.delete_moment_comment(moment_id=123, comment_id=456)

    assert result == {"ok": True}
    assert api_server.last_path == "/v1/moments/123/comments/456"


def test_base_url_requires_http_scheme():
    with pytest.raises(ClawChatApiError):
        ClawChatApiClient(base_url="ws://bad")
