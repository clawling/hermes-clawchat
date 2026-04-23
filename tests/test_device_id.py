from __future__ import annotations

from types import SimpleNamespace

from clawchat_gateway import device_id


def test_device_id_uses_env_override(monkeypatch):
    device_id.get_device_id.cache_clear()
    monkeypatch.setenv("CLAWCHAT_DEVICE_ID", "dev box 1")

    assert device_id.get_device_id() == "hermes-dev-box-1"


def test_device_id_keeps_prefixed_env_override(monkeypatch):
    device_id.get_device_id.cache_clear()
    monkeypatch.setenv("CLAWCHAT_DEVICE_ID", "hermes-custom-device")

    assert device_id.get_device_id() == "hermes-custom-device"


def test_mac_device_id_uses_platform_uuid(monkeypatch):
    device_id.get_device_id.cache_clear()
    monkeypatch.delenv("CLAWCHAT_DEVICE_ID", raising=False)
    monkeypatch.setattr(device_id.platform, "system", lambda: "Darwin")

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(stdout='    "IOPlatformUUID" = "ABCDEF12-3456-7890-ABCD-EF1234567890"\n')

    monkeypatch.setattr(device_id.subprocess, "run", fake_run)

    assert device_id.get_device_id() == "hermes-mac-abcdef12-3456-7890-abcd-ef1234567890"
