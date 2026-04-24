from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


class _Ctx:
    def __init__(self) -> None:
        self.tools = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}


def _load_plugin_module():
    plugin_path = (
        Path(__file__).resolve().parents[1]
        / "hermes_plugin"
        / "clawchat-tools"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("clawchat_tools_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plugin_registers_all_tools():
    module = _load_plugin_module()
    ctx = _Ctx()

    module.register(ctx)

    assert set(ctx.tools) == {
        "clawchat_activate",
        "clawchat_get_my_profile",
        "clawchat_get_user_info",
        "clawchat_list_friends",
        "clawchat_update_my_profile",
        "clawchat_upload_avatar",
        "clawchat_upload_file",
    }
    assert all(ctx.tools[name]["is_async"] is True for name in ctx.tools)


def test_activate_schema_triggers_on_chinese_activation_code_phrase():
    module = _load_plugin_module()
    ctx = _Ctx()
    module.register(ctx)

    schema = ctx.tools["clawchat_activate"]["schema"]
    description = schema["description"]
    code_description = schema["parameters"]["properties"]["code"]["description"]

    assert "clawchat 的激活码是 R4E1IW" in description
    assert "code = \"R4E1IW\"" in description
    assert "Do not ask for baseUrl" in description
    assert "does not provide a code yet" in description
    assert "Hermes must be restarted" in description
    assert "clawchat 的激活码是" in code_description


def test_plugin_upload_file_rejects_relative_path():
    module = _load_plugin_module()
    ctx = _Ctx()
    module.register(ctx)

    result = asyncio.run(ctx.tools["clawchat_upload_file"]["handler"]({"filePath": "relative.png"}))

    assert result["kind"] == "validation"
    assert "absolute local path" in result["error"]


def test_activate_uses_base_url_override_and_persists_it(monkeypatch):
    module = _load_plugin_module()
    ctx = _Ctx()
    writes = []
    calls = []

    monkeypatch.setattr(module, "_load_plugin_config", lambda: (Path("/tmp/hermes-config.yaml"), {}))

    def fake_write(path, config):
        writes.append({"path": path, "config": config})

    class FakeClient:
        def __init__(self, *, base_url, token="", user_id="", device_id=""):
            calls.append({"base_url": base_url, "token": token, "user_id": user_id})

        async def agents_connect(self, *, code, tools=None):
            calls.append({"code": code, "tools": tools})
            return {
                "access_token": "tk",
                "refresh_token": "rt",
                "agent": {"user_id": "agent-1"},
            }

    monkeypatch.setattr(module, "_write_plugin_config", fake_write)
    monkeypatch.setattr(module, "ClawChatApiClient", FakeClient)

    module.register(ctx)
    result = asyncio.run(
        ctx.tools["clawchat_activate"]["handler"](
            {
                "code": "R4E1IW",
                "baseUrl": "https://api.example.com",
                "tools": ["clawchat_get_my_profile"],
            }
        )
    )

    assert result["ok"] is True
    assert result["refresh_token"] == "***"
    assert result["restart_required"] is True
    assert "Restart Hermes gateway" in result["restart_message"]
    assert calls == [
        {"base_url": "https://api.example.com", "token": "", "user_id": ""},
        {"code": "R4E1IW", "tools": ["clawchat_get_my_profile"]},
    ]
    assert writes[0]["config"]["platforms"]["clawchat"]["extra"]["base_url"] == "https://api.example.com"
    assert writes[0]["config"]["platforms"]["clawchat"]["extra"]["websocket_url"] == "wss://api.example.com/v1/ws"
    assert writes[0]["config"]["platforms"]["clawchat"]["extra"]["reply_mode"] == "stream"
    assert writes[0]["config"]["platforms"]["clawchat"]["extra"]["show_tools_output"] is False
    assert writes[0]["config"]["platforms"]["clawchat"]["extra"]["show_think_output"] is False
    assert writes[0]["config"]["streaming"]["enabled"] is True
    assert writes[0]["config"]["display"]["platforms"]["clawchat"]["tool_progress"] == "off"
    assert writes[0]["config"]["display"]["platforms"]["clawchat"]["show_reasoning"] is False


def test_activate_defaults_to_real_newbase_endpoints(monkeypatch):
    module = _load_plugin_module()
    ctx = _Ctx()
    writes = []

    monkeypatch.setattr(module, "_load_plugin_config", lambda: (Path("/tmp/hermes-config.yaml"), {}))
    monkeypatch.setattr(module, "_write_plugin_config", lambda path, config: writes.append(config))

    class FakeClient:
        def __init__(self, *, base_url, token="", user_id="", device_id=""):
            assert base_url == "http://company.newbaselab.com:10086"

        async def agents_connect(self, *, code, tools=None):
            return {
                "access_token": "tk",
                "refresh_token": "rt",
                "agent": {"user_id": "agent-1"},
            }

    monkeypatch.setattr(module, "ClawChatApiClient", FakeClient)

    module.register(ctx)
    result = asyncio.run(ctx.tools["clawchat_activate"]["handler"]({"code": "R4E1IW"}))

    assert result["ok"] is True
    assert result["restart_required"] is True
    extra = writes[0]["platforms"]["clawchat"]["extra"]
    assert extra["base_url"] == "http://company.newbaselab.com:10086"
    assert extra["websocket_url"] == "ws://company.newbaselab.com:10086/ws"
    assert extra["reply_mode"] == "stream"
    assert extra["show_tools_output"] is False
    assert extra["show_think_output"] is False
    assert writes[0]["streaming"]["enabled"] is True
    assert writes[0]["display"]["platforms"]["clawchat"]["tool_progress"] == "off"
    assert writes[0]["display"]["platforms"]["clawchat"]["show_reasoning"] is False
