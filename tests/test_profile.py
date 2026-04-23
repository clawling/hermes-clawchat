from __future__ import annotations

import pytest
import yaml

from clawchat_gateway.profile import ProfileConfigError, load_profile_config, update_avatar, update_nickname
from tests.test_api_client import api_server


@pytest.mark.asyncio
async def test_update_nickname_loads_config_and_patches_user(api_server, monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "platforms": {
                    "clawchat": {
                        "extra": {
                            "base_url": f"http://127.0.0.1:{api_server.server_port}",
                            "token": "token-bob",
                            "user_id": "user-1",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = await update_nickname("Hermes Bot")

    assert result["updated"] == {"nickname": "Hermes Bot"}
    assert result["profile"]["nickname"] == "Hermes Bot"
    assert api_server.captured == {"nickname": "Hermes Bot"}


@pytest.mark.asyncio
async def test_update_avatar_uploads_local_file_then_patches_user(api_server, monkeypatch, tmp_path):
    avatar_path = tmp_path / "avatar.png"
    avatar_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "platforms": {
                    "clawchat": {
                        "extra": {
                            "base_url": f"http://127.0.0.1:{api_server.server_port}",
                            "token": "token-bob",
                            "user_id": "user-1",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = await update_avatar(str(avatar_path))

    assert result["uploaded"]["url"] == "https://cdn/avatar.png"
    assert result["updated"] == {"avatar_url": "https://cdn/avatar.png"}
    assert api_server.captured == {"avatar_url": "https://cdn/avatar.png"}
    assert api_server.paths == ["/v1/files/upload-url", "/v1/users/me"]


def test_load_profile_config_requires_token(monkeypatch, tmp_path):
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"platforms": {"clawchat": {"extra": {"base_url": "http://127.0.0.1:1"}}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    with pytest.raises(ProfileConfigError, match="token"):
        load_profile_config()


@pytest.mark.asyncio
async def test_update_avatar_requires_absolute_local_path(monkeypatch, tmp_path):
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "platforms": {
                    "clawchat": {
                        "extra": {
                            "base_url": "http://127.0.0.1:1",
                            "token": "token-bob",
                            "user_id": "user-1",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    with pytest.raises(ProfileConfigError, match="absolute"):
        await update_avatar("avatar.png")
