from pathlib import Path

import yaml

from clawchat_gateway.activate import persist_activation


def test_persist_activation_writes_clawchat_config(tmp_path: Path, monkeypatch) -> None:
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
    assert extra["token"] == "tk"
    assert extra["refresh_token"] == "rt"
    assert extra["user_id"] == "agent-1"
    assert extra["websocket_url"] == "ws://company.newbaselab.com:10086/ws"
    assert config["display"]["platforms"]["clawchat"]["tool_progress"] == "off"
    assert result["restart_required"] is True
