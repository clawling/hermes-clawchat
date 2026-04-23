from __future__ import annotations

import importlib.util
from pathlib import Path


class _Ctx:
    def __init__(self) -> None:
        self.tools = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            **kwargs,
        }

    def register_skill(self, name, path, description=""):
        self.skills[name] = {"path": path, "description": description}


def _load_root_plugin():
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("clawchat_git_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_git_plugin_registers_tools_and_skill(monkeypatch):
    module = _load_root_plugin()
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(module, "_install_gateway", lambda: None)
    ctx = _Ctx()

    module.register(ctx)

    assert set(ctx.tools) == {
        "clawchat_activate",
        "clawchat_update_nickname",
        "clawchat_update_avatar",
    }
    assert ctx.tools["clawchat_activate"]["toolset"] == "clawchat"
    assert ctx.tools["clawchat_activate"]["is_async"] is True
    assert ctx.tools["clawchat_update_nickname"]["is_async"] is True
    assert ctx.tools["clawchat_update_avatar"]["is_async"] is True
    assert "upload" in ctx.tools["clawchat_update_avatar"]["schema"]["description"]
    assert "/v1/files/upload-url" in ctx.tools["clawchat_update_avatar"]["schema"]["description"]
    assert "clawchat" in ctx.skills
