import asyncio
import importlib
import sys
import types
from pathlib import Path


def _install_hermes_config_helpers(
    monkeypatch,
    hermes_home: Path,
    *,
    initial_config: dict | None = None,
) -> tuple[dict[str, str], list[str], list[dict]]:
    saved_env: dict[str, str] = {}
    removed_env: list[str] = []
    saved_configs: list[dict] = []
    config_module = types.ModuleType("hermes_cli.config")
    config_module.get_config_path = lambda: hermes_home / "config.yaml"
    config_module.get_env_path = lambda: hermes_home / ".env"
    config_module.read_raw_config = lambda: initial_config or {}
    config_module.save_config = lambda config: saved_configs.append(config)
    config_module.save_env_value = lambda key, value: saved_env.__setitem__(key, value)
    config_module.remove_env_value = lambda key: removed_env.append(key) or True
    hermes_module = types.ModuleType("hermes_cli")
    hermes_module.config = config_module
    monkeypatch.setitem(sys.modules, "hermes_cli", hermes_module)
    monkeypatch.setitem(sys.modules, "hermes_cli.config", config_module)
    return saved_env, removed_env, saved_configs


def _load_activate_with_hermes_config_helpers(
    monkeypatch,
    hermes_home: Path,
    *,
    initial_config: dict | None = None,
):
    saved_env, removed_env, saved_configs = _install_hermes_config_helpers(
        monkeypatch,
        hermes_home,
        initial_config=initial_config,
    )
    activate_mod = importlib.import_module("clawchat_gateway.activate")
    activate_mod = importlib.reload(activate_mod)
    return activate_mod, saved_env, removed_env, saved_configs


def test_activation_module_requires_hermes_config_helpers(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "hermes_cli", types.ModuleType("hermes_cli"))
    monkeypatch.delitem(sys.modules, "hermes_cli.config", raising=False)
    monkeypatch.delitem(sys.modules, "clawchat_gateway.activate", raising=False)

    try:
        importlib.import_module("clawchat_gateway.activate")
    except RuntimeError as exc:
        assert "hermes_cli.config" in str(exc)
    else:
        raise AssertionError("activate module should require hermes_cli.config")


def test_activation_module_binds_official_config_helpers_at_import(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_home = tmp_path / ".hermes"
    _install_hermes_config_helpers(monkeypatch, hermes_home)

    activate_mod = importlib.import_module("clawchat_gateway.activate")
    activate_mod = importlib.reload(activate_mod)
    config_mod = sys.modules["hermes_cli.config"]

    assert activate_mod.get_config_path is config_mod.get_config_path
    assert activate_mod.save_config is config_mod.save_config
    assert activate_mod.save_env_value is config_mod.save_env_value
    assert not hasattr(activate_mod, "_hermes_config_api")


def test_activation_module_is_not_a_cli_script(tmp_path: Path, monkeypatch) -> None:
    hermes_home = tmp_path / ".hermes"
    activate_mod, _saved_env, _removed_env, _saved_configs = _load_activate_with_hermes_config_helpers(
        monkeypatch,
        hermes_home,
    )

    assert not hasattr(activate_mod, "main")


def test_persist_activation_writes_secrets_to_env_and_config_without_secrets(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    activate_mod, saved_env, removed_env, saved_configs = _load_activate_with_hermes_config_helpers(
        monkeypatch,
        hermes_home,
    )

    result = activate_mod.persist_activation(
        access_token="tk",
        refresh_token="rt",
        user_id="agent-1",
        base_url="https://app.clawling.com",
    )

    assert saved_env == {"CLAWCHAT_TOKEN": "tk", "CLAWCHAT_REFRESH_TOKEN": "rt"}
    assert removed_env == []
    assert len(saved_configs) == 1
    config = saved_configs[0]
    extra = config["platforms"]["clawchat"]["extra"]
    assert "token" not in extra
    assert "refresh_token" not in extra
    assert extra["user_id"] == "agent-1"
    assert extra["websocket_url"] == "wss://app.clawling.com/ws"
    assert config["display"]["platforms"]["clawchat"]["tool_progress"] == "off"
    assert result["restart_required"] is True


def test_persist_activation_removes_stale_config_secrets_and_refresh_env(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    activate_mod, saved_env, removed_env, saved_configs = _load_activate_with_hermes_config_helpers(
        monkeypatch,
        hermes_home,
        initial_config={
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
        },
    )

    activate_mod.persist_activation(
        access_token="new-token",
        refresh_token=None,
        user_id="agent-2",
        base_url="https://chat.example",
    )

    assert saved_env == {"CLAWCHAT_TOKEN": "new-token"}
    assert removed_env == ["CLAWCHAT_REFRESH_TOKEN"]
    assert len(saved_configs) == 1
    config = saved_configs[0]
    extra = config["platforms"]["clawchat"]["extra"]
    assert "token" not in extra
    assert "refresh_token" not in extra
    assert extra["user_id"] == "agent-2"
    assert extra["websocket_url"] == "wss://chat.example/ws"


def test_persist_activation_uses_hermes_config_helpers_when_available(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    activate_mod, saved_env, removed_env, saved_configs = _load_activate_with_hermes_config_helpers(
        monkeypatch,
        hermes_home,
        initial_config={
            "platforms": {
                "clawchat": {
                    "enabled": True,
                    "extra": {
                        "token": "old-yaml",
                        "refresh_token": "old-refresh",
                    },
                }
            }
        },
    )

    result = activate_mod.persist_activation(
        access_token="new-token",
        refresh_token=None,
        user_id="agent-3",
        base_url="https://chat.example",
    )

    assert saved_env == {"CLAWCHAT_TOKEN": "new-token"}
    assert removed_env == ["CLAWCHAT_REFRESH_TOKEN"]
    assert len(saved_configs) == 1
    extra = saved_configs[0]["platforms"]["clawchat"]["extra"]
    assert "token" not in extra
    assert "refresh_token" not in extra
    assert extra["user_id"] == "agent-3"
    assert result["config_path"] == str(hermes_home / "config.yaml")
    assert result["env_path"] == str(hermes_home / ".env")


def test_activate_and_maybe_restart_schedules_restart(monkeypatch, tmp_path: Path) -> None:
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    from clawchat_gateway import activate as activate_mod

    async def fake_activate(code: str, *, base_url: str):
        assert code == "ABC123"
        assert base_url == "https://chat.example"
        return {
            "config_path": str(hermes_home / "config.yaml"),
            "env_path": str(hermes_home / ".env"),
            "user_id": "agent-1",
            "base_url": base_url,
            "websocket_url": "wss://chat.example/ws",
            "token": "***",
            "refresh_token": "***",
            "restart_required": True,
            "restart_message": "Restart Hermes gateway so ClawChat reloads the new credentials.",
        }

    monkeypatch.setattr(activate_mod, "activate", fake_activate)
    monkeypatch.setattr(
        activate_mod,
        "schedule_gateway_restart",
        lambda delay_seconds=2: f"restart after {delay_seconds}",
        raising=False,
    )

    result = asyncio.run(
        activate_mod.activate_and_maybe_restart(
            "ABC123",
            base_url="https://chat.example",
            restart=True,
        )
    )

    assert result["ok"] is True
    assert result["restart_scheduled"] is True
    assert result["restart_delay_seconds"] == 2
    assert result["restart_command"] == "restart after 2"
    assert result["restart_message"] == (
        "ClawChat activation is saved. Hermes restart has been scheduled in the background."
    )


def test_activate_and_maybe_restart_can_skip_restart(monkeypatch, tmp_path: Path) -> None:
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    from clawchat_gateway import activate as activate_mod

    async def fake_activate(code: str, *, base_url: str):
        return {
            "config_path": str(hermes_home / "config.yaml"),
            "env_path": str(hermes_home / ".env"),
            "user_id": "agent-1",
            "base_url": base_url,
            "websocket_url": "wss://chat.example/ws",
            "token": "***",
            "refresh_token": None,
            "restart_required": True,
            "restart_message": "Restart Hermes gateway so ClawChat reloads the new credentials.",
        }

    monkeypatch.setattr(activate_mod, "activate", fake_activate)

    def fail_restart(delay_seconds=2):
        raise AssertionError("restart should not be scheduled")

    monkeypatch.setattr(activate_mod, "schedule_gateway_restart", fail_restart, raising=False)

    result = asyncio.run(
        activate_mod.activate_and_maybe_restart(
            "ABC123",
            base_url="https://chat.example",
            restart=False,
        )
    )

    assert result["ok"] is True
    assert "restart_scheduled" not in result
    assert result["restart_required"] is True
