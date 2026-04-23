from __future__ import annotations

from pathlib import Path

from clawchat_gateway.install import (
    Patch,
    _read_state,
    _state_file,
    _write_state,
    apply_patch,
    build_patches,
    configure_clawchat_allow_all,
    configure_clawchat_streaming,
    clear_skills_prompt_snapshot,
    install_plugin,
    patch_applied,
    plugin_installed,
    remove_patch,
    uninstall_plugin,
)


def test_build_patches_contains_expected_ids(tmp_path: Path) -> None:
    patches = build_patches(tmp_path)
    patch_ids = {patch.id for patch in patches}
    assert {
        "platform_enum",
        "env_overrides",
        "connected_platforms",
        "adapter_factory",
        "auth_maps_allowed",
        "auth_maps_allow_all",
        "prompt_hints",
        "post_stream_hook",
        "normal_stream_done_hook",
        "send_message_tool",
        "cli_platform_registry",
        "startup_any_allowlist",
        "startup_allow_all",
        "update_allowed_platforms",
    } <= patch_ids


def test_apply_and_remove_patch_with_indentation(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text('    QQBOT = "qqbot"\n')
    patch = Patch(
        id="platform_enum",
        file=str(target),
        anchor='QQBOT = "qqbot"',
        payload='CLAWCHAT = "clawchat"\n',
        indent_to_anchor=True,
    )

    assert apply_patch(patch) is True
    content = target.read_text()
    assert '    # clawchat-gateway:platform_enum:start\n' in content
    assert '    CLAWCHAT = "clawchat"\n' in content
    assert patch_applied(patch) is True

    assert remove_patch(patch) is True
    assert target.read_text() == '    QQBOT = "qqbot"\n'


def test_cli_platform_registry_patch_inserts_clawchat(tmp_path: Path) -> None:
    target = tmp_path / "platforms.py"
    target.write_text(
        "PLATFORMS = OrderedDict([\n"
        '    ("qqbot",          PlatformInfo(label="QQBot", default_toolset="hermes-qqbot")),\n'
        "])\n"
    )
    patch = next(patch for patch in build_patches(tmp_path) if patch.id == "cli_platform_registry")
    patch.file = str(target)

    assert apply_patch(patch) is True
    content = target.read_text()
    assert '"clawchat"' in content
    assert 'default_toolset="hermes-cli"' in content
    assert patch_applied(patch) is True


def test_install_state_round_trip(tmp_path: Path) -> None:
    _write_state(tmp_path, ["platform_enum", "adapter_factory"])
    state = _read_state(tmp_path)
    assert state is not None
    assert state["patches_applied"] == ["platform_enum", "adapter_factory"]
    assert _state_file(tmp_path).exists()


def test_install_and_uninstall_skill(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes-home"))
    legacy = tmp_path / ".hermes-home" / "plugins" / "clawchat-tools"
    legacy.mkdir(parents=True)
    (legacy / "plugin.yaml").write_text("name: clawchat-tools\n")
    assert install_plugin(tmp_path) is True
    assert plugin_installed(tmp_path) is True
    assert (
        tmp_path / ".hermes-home" / "skills" / "clawchat" / "SKILL.md"
    ).exists()
    assert not legacy.exists()
    assert uninstall_plugin(tmp_path) is True
    assert plugin_installed(tmp_path) is False


def test_configure_clawchat_allow_all_writes_env(tmp_path: Path, monkeypatch) -> None:
    hermes_home = tmp_path / ".hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    assert configure_clawchat_allow_all() is True
    assert (hermes_home / ".env").read_text() == "CLAWCHAT_ALLOW_ALL_USERS=true\n"

    assert configure_clawchat_allow_all() is False
    assert (hermes_home / ".env").read_text() == "CLAWCHAT_ALLOW_ALL_USERS=true\n"


def test_clear_skills_prompt_snapshot(tmp_path: Path, monkeypatch) -> None:
    hermes_home = tmp_path / ".hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    hermes_home.mkdir()
    snapshot = hermes_home / ".skills_prompt_snapshot.json"
    snapshot.write_text("{}")

    assert clear_skills_prompt_snapshot() is True
    assert not snapshot.exists()
    assert clear_skills_prompt_snapshot() is False


def test_configure_clawchat_allow_all_updates_existing_env(tmp_path: Path, monkeypatch) -> None:
    hermes_home = tmp_path / ".hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    hermes_home.mkdir()
    (hermes_home / ".env").write_text("KIMI_BASE_URL=https://api.kimi.com/coding/v1\nCLAWCHAT_ALLOW_ALL_USERS=false\n")

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
