from pathlib import Path

import yaml

from clawchat_gateway.activate import persist_activation


def _read_env(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if line and not line.startswith("#")
    )


def test_persist_activation_writes_secrets_to_env_and_config_without_secrets(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    result = persist_activation(
        access_token="tk",
        refresh_token="rt",
        user_id="agent-1",
        base_url="http://company.newbaselab.com:10086",
    )

    config = yaml.safe_load((hermes_home / "config.yaml").read_text())
    extra = config["platforms"]["clawchat"]["extra"]
    env = _read_env(hermes_home / ".env")
    assert env["CLAWCHAT_TOKEN"] == "tk"
    assert env["CLAWCHAT_REFRESH_TOKEN"] == "rt"
    assert "token" not in extra
    assert "refresh_token" not in extra
    assert extra["user_id"] == "agent-1"
    assert extra["websocket_url"] == "ws://company.newbaselab.com:10086/ws"
    assert config["display"]["platforms"]["clawchat"]["tool_progress"] == "off"
    assert result["restart_required"] is True


def test_persist_activation_removes_stale_config_secrets_and_refresh_env(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    hermes_home.mkdir()
    (hermes_home / ".env").write_text(
        "KIMI_BASE_URL=https://api.kimi.com/coding/v1\n"
        "CLAWCHAT_TOKEN=old\n"
        "CLAWCHAT_REFRESH_TOKEN=stale\n"
        "OTHER=value\n"
    )
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "platforms": {
                    "clawchat": {
                        "enabled": True,
                        "extra": {
                            "token": "old-yaml",
                            "refresh_token": "old-refresh",
                            "user_id": "old-user",
                        },
                    }
                }
            }
        )
    )

    persist_activation(
        access_token="new-token",
        refresh_token=None,
        user_id="agent-2",
        base_url="https://chat.example",
    )

    config = yaml.safe_load((hermes_home / "config.yaml").read_text())
    extra = config["platforms"]["clawchat"]["extra"]
    env = _read_env(hermes_home / ".env")
    assert env["CLAWCHAT_TOKEN"] == "new-token"
    assert "CLAWCHAT_REFRESH_TOKEN" not in env
    assert env["KIMI_BASE_URL"] == "https://api.kimi.com/coding/v1"
    assert env["OTHER"] == "value"
    assert "token" not in extra
    assert "refresh_token" not in extra
    assert extra["user_id"] == "agent-2"
    assert extra["websocket_url"] == "wss://chat.example/v1/ws"
