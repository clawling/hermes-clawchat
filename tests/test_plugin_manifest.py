from pathlib import Path
import tomllib

import yaml


def test_plugin_manifest_declares_v012_platform_credentials():
    manifest = yaml.safe_load((Path(__file__).resolve().parents[1] / "plugin.yaml").read_text())

    assert manifest["kind"] == "platform"
    assert manifest["requires_env"] == ["CLAWCHAT_TOKEN", "CLAWCHAT_REFRESH_TOKEN"]
    assert manifest["provides_tools"] == [
        "clawchat_get_account_profile",
        "clawchat_get_user_profile",
        "clawchat_list_account_friends",
        "clawchat_update_account_profile",
        "clawchat_upload_avatar_image",
        "clawchat_upload_media_file",
    ]


def test_package_exposes_no_legacy_anchor_patch_console_script():
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())

    assert pyproject["project"].get("scripts", {}) == {}
