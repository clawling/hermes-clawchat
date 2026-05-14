from __future__ import annotations

from pathlib import Path

from clawchat_gateway.runtime_defaults import (
    configure_clawchat_allow_all,
    configure_clawchat_streaming,
)


def test_configure_clawchat_allow_all_writes_env(tmp_path: Path, monkeypatch) -> None:
    hermes_home = tmp_path / ".hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    assert configure_clawchat_allow_all() is True
    assert (hermes_home / ".env").read_text() == "CLAWCHAT_ALLOW_ALL_USERS=true\n"

    assert configure_clawchat_allow_all() is False
    assert (hermes_home / ".env").read_text() == "CLAWCHAT_ALLOW_ALL_USERS=true\n"


def test_configure_clawchat_allow_all_updates_existing_env(tmp_path: Path, monkeypatch) -> None:
    hermes_home = tmp_path / ".hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    hermes_home.mkdir()
    (hermes_home / ".env").write_text(
        "KIMI_BASE_URL=https://api.kimi.com/coding/v1\nCLAWCHAT_ALLOW_ALL_USERS=false\n"
    )

    assert configure_clawchat_allow_all() is True
    assert (hermes_home / ".env").read_text() == (
        "KIMI_BASE_URL=https://api.kimi.com/coding/v1\n"
        "CLAWCHAT_ALLOW_ALL_USERS=true\n"
    )


def test_configure_clawchat_streaming_writes_config(tmp_path: Path, monkeypatch) -> None:
    hermes_home = tmp_path / ".hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "platforms:\n"
        "  clawchat:\n"
        "    enabled: true\n"
        "    extra:\n"
        "      token: tk\n"
        "streaming:\n"
        "  enabled: false\n"
    )

    assert configure_clawchat_streaming() is True
    content = (hermes_home / "config.yaml").read_text()
    assert "reply_mode: stream" in content
    assert "show_tools_output: false" in content
    assert "show_think_output: false" in content
    assert "enabled: true" in content
    assert "transport: edit" in content
    assert "edit_interval: 0.25" in content
    assert "buffer_threshold: 16" in content
    assert "tool_progress: 'off'" in content or "tool_progress: off" in content
    assert "show_reasoning: false" in content

    assert configure_clawchat_streaming() is False
