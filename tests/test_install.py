from __future__ import annotations

import json
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
    main as install_main,
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
        "env_overrides_refresh_token",
        "prompt_hints",
        "post_stream_hook",
        "normal_stream_done_hook",
        "send_message_tool",
        "cli_platform_registry",
        "cron_known_delivery_platforms",
        "cron_platform_map",
        "startup_any_allowlist",
        "startup_allow_all",
        "startup_allow_all_yuanbao",
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


def test_env_overrides_patch_reads_refresh_token(tmp_path: Path) -> None:
    gateway_dir = tmp_path / "gateway"
    gateway_dir.mkdir()
    target = gateway_dir / "config.py"
    target.write_text("# Session settings\n")
    patches = {patch.id: patch for patch in build_patches(tmp_path)}

    assert apply_patch(patches["env_overrides"]) is True
    assert apply_patch(patches["env_overrides_refresh_token"]) is True
    content = target.read_text()
    assert 'os.getenv("CLAWCHAT_REFRESH_TOKEN", "").strip()' in content
    assert 'if clawchat_refresh_token: _ce["refresh_token"] = clawchat_refresh_token' in content


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


def test_cron_scheduler_patches_insert_clawchat(tmp_path: Path) -> None:
    target = tmp_path / "scheduler.py"
    target.write_text(
        "_KNOWN_DELIVERY_PLATFORMS = frozenset({\n"
        '    "qqbot",\n'
        "})\n"
        "\n"
        "    platform_map = {\n"
        '        "qqbot": Platform.QQBOT,\n'
        "    }\n"
    )
    patches = {p.id: p for p in build_patches(tmp_path)}

    known = patches["cron_known_delivery_platforms"]
    known.file = str(target)
    pmap = patches["cron_platform_map"]
    pmap.file = str(target)

    assert apply_patch(known) is True
    assert apply_patch(pmap) is True
    content = target.read_text()
    assert '"clawchat",\n' in content
    assert '"clawchat": Platform.CLAWCHAT,\n' in content
    assert patch_applied(known) is True
    assert patch_applied(pmap) is True


def test_startup_allow_all_patch_handles_yuanbao_allow_all_anchor(tmp_path: Path) -> None:
    target = tmp_path / "run.py"
    target.write_text(
        "        _allow_all = any(\n"
        "            os.getenv(v, '').lower() in ('true', '1', 'yes')\n"
        "            for v in (\"TELEGRAM_ALLOW_ALL_USERS\",\n"
        "                       \"QQ_ALLOW_ALL_USERS\",\n"
        "                       \"YUANBAO_ALLOW_ALL_USERS\")\n"
        "        )\n"
    )
    patch = next(patch for patch in build_patches(tmp_path) if patch.id == "startup_allow_all_yuanbao")
    patch.file = str(target)

    assert apply_patch(patch) is True
    content = target.read_text()
    assert '"CLAWCHAT_ALLOW_ALL_USERS",\n' in content
    assert content.index('"QQ_ALLOW_ALL_USERS"') < content.index('"CLAWCHAT_ALLOW_ALL_USERS"')
    assert content.index('"CLAWCHAT_ALLOW_ALL_USERS"') < content.index('"YUANBAO_ALLOW_ALL_USERS"')


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


def test_package_init_does_not_eagerly_import_adapter() -> None:
    """The ``clawchat_gateway`` package must not eagerly import ``adapter``.

    ``adapter`` binds ``Platform`` at module scope via
    ``from gateway.config import Platform``. If the package ``__init__`` pulls
    it in at plugin register time (before we apply the platform_enum patch),
    the adapter's ``Platform`` reference is stale — even after we reload
    ``gateway.config``, ``super().__init__(..., Platform.CLAWCHAT)`` would
    raise ``AttributeError`` once the gateway tries to construct the
    adapter.
    """
    import sys

    saved = {k: v for k, v in sys.modules.items() if k.startswith("clawchat_gateway")}
    for mod_name in list(saved):
        del sys.modules[mod_name]

    try:
        import clawchat_gateway  # noqa: F401

        assert "clawchat_gateway.adapter" not in sys.modules
        assert "clawchat_gateway" in sys.modules
    finally:
        for mod_name in [m for m in list(sys.modules) if m.startswith("clawchat_gateway")]:
            del sys.modules[mod_name]
        sys.modules.update(saved)


def test_install_rolls_back_when_anchor_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    """If any non-soft-fail patch has a missing anchor, every patch applied
    in the same run must be reverted. Otherwise hermes-agent is left with
    e.g. `Platform.CLAWCHAT,` in run.py but no `CLAWCHAT` member on the enum.
    """
    hermes_dir = tmp_path / "hermes-agent"
    (hermes_dir / "gateway").mkdir(parents=True)
    (hermes_dir / "agent").mkdir(parents=True)
    (hermes_dir / "tools").mkdir(parents=True)
    (hermes_dir / "hermes_cli").mkdir(parents=True)

    # Present: anchors for the FIRST config.py patch and the adapter_factory
    # patch in run.py — these should apply, then get rolled back.
    (hermes_dir / "gateway" / "config.py").write_text(
        'class Platform(str, Enum):\n    QQBOT = "qqbot"\n'
    )
    # Deliberately omit the anchor for `connected_platforms` so mid-run
    # failure triggers rollback.
    (hermes_dir / "gateway" / "run.py").write_text(
        "elif platform == Platform.QQBOT:\n    pass\n"
    )
    (hermes_dir / "agent" / "prompt_builder.py").write_text("")
    (hermes_dir / "tools" / "send_message_tool.py").write_text("")
    (hermes_dir / "hermes_cli" / "platforms.py").write_text("")

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes-home"))

    rc = install_main(["--hermes-dir", str(hermes_dir)])
    assert rc == 1

    err = capsys.readouterr().err
    report = json.loads(err.strip())
    assert report["error"] == "failed_to_apply_some_patches"
    assert "platform_enum" in report["rolled_back"]

    # The partially-applied patches must be gone from disk.
    config_text = (hermes_dir / "gateway" / "config.py").read_text()
    assert "clawchat-gateway:platform_enum:start" not in config_text
    assert 'CLAWCHAT = "clawchat"' not in config_text
    run_text = (hermes_dir / "gateway" / "run.py").read_text()
    assert "clawchat-gateway:adapter_factory:start" not in run_text


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
