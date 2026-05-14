from pathlib import Path
import tomllib

import yaml


def test_plugin_manifest_declares_v012_platform_credentials():
    manifest = yaml.safe_load((Path(__file__).resolve().parents[1] / "plugin.yaml").read_text())

    assert manifest["kind"] == "platform"
    assert manifest["requires_env"] == ["CLAWCHAT_TOKEN", "CLAWCHAT_REFRESH_TOKEN"]


def test_package_exposes_no_legacy_anchor_patch_console_script():
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())

    assert pyproject["project"].get("scripts", {}) == {}
