from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


class _Ctx:
    def __init__(self) -> None:
        self.tools = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}

    def register_skill(self, name, path, description=""):
        self.skills[name] = {"path": path, "description": description}


def _load_plugin_module():
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("clawchat_tools_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plugin_registers_all_tools(monkeypatch):
    module = _load_plugin_module()
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(module, "_install_gateway", lambda: None)
    ctx = _Ctx()

    module.register(ctx)

    assert set(ctx.tools) == {
        "clawchat_activate",
        "clawchat_get_account_profile",
        "clawchat_get_user_profile",
        "clawchat_list_account_friends",
        "clawchat_update_account_profile",
        "clawchat_upload_avatar_image",
        "clawchat_upload_media_file",
    }
    assert all(ctx.tools[name]["is_async"] is True for name in ctx.tools)


def test_activate_schema_triggers_on_chinese_activation_code_phrase(monkeypatch):
    module = _load_plugin_module()
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(module, "_install_gateway", lambda: None)
    ctx = _Ctx()
    module.register(ctx)

    schema = ctx.tools["clawchat_activate"]["schema"]
    description = schema["description"]
    code_description = schema["parameters"]["properties"]["code"]["description"]

    assert "clawchat 的激活码是 R4E1IW" in description
    assert "Extract the code verbatim" in description
    assert "connect-codes" in description
    assert "clawchat 的激活码是" in code_description


def test_plugin_upload_avatar_image_rejects_relative_path(monkeypatch):
    module = _load_plugin_module()
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(module, "_install_gateway", lambda: None)
    ctx = _Ctx()
    module.register(ctx)

    result = asyncio.run(ctx.tools["clawchat_upload_avatar_image"]["handler"]({"filePath": "relative.png"}))

    assert result["error"] == "validation"
    assert "absolute local path" in result["message"]
