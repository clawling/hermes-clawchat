from pathlib import Path

import yaml


def test_plugin_manifest_declares_v012_platform_credentials():
    manifest = yaml.safe_load((Path(__file__).resolve().parents[1] / "plugin.yaml").read_text())

    assert manifest["kind"] == "platform"
    assert manifest["requires_env"] == ["CLAWCHAT_TOKEN", "CLAWCHAT_REFRESH_TOKEN"]
