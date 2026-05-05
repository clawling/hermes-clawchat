from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import yaml


class _Ctx:
    def __init__(self) -> None:
        self.tools = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}

    def register_skill(self, name, path, description=""):
        self.skills[name] = {"path": path, "description": description}


class _PlatformCtx(_Ctx):
    def __init__(self) -> None:
        super().__init__()
        self.platforms = {}

    def register_platform(
        self,
        name,
        label,
        adapter_factory,
        check_fn,
        validate_config=None,
        required_env=None,
        install_hint="",
        **kwargs,
    ):
        self.platforms[name] = {
            "label": label,
            "adapter_factory": adapter_factory,
            "check_fn": check_fn,
            "validate_config": validate_config,
            "required_env": required_env,
            "install_hint": install_hint,
            **kwargs,
        }


def _load_plugin_module():
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("clawchat_tools_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plugin_registers_clawchat_platform_with_registry(monkeypatch):
    module = _load_plugin_module()
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(
        module,
        "_install_gateway",
        lambda: (_ for _ in ()).throw(AssertionError("installer should not run")),
    )
    monkeypatch.setattr(module, "_configure_runtime_defaults", lambda: None, raising=False)
    ctx = _PlatformCtx()

    module.register(ctx)

    platform = ctx.platforms["clawchat"]
    assert platform["label"] == "ClawChat"
    assert callable(platform["adapter_factory"])
    assert callable(platform["check_fn"])
    assert callable(platform["validate_config"])
    assert callable(platform["is_connected"])
    assert platform["required_env"] == ["CLAWCHAT_TOKEN", "CLAWCHAT_REFRESH_TOKEN"]
    assert platform["allowed_users_env"] == "CLAWCHAT_ALLOWED_USERS"
    assert platform["allow_all_env"] == "CLAWCHAT_ALLOW_ALL_USERS"
    assert "ClawChat" in platform["platform_hint"]
    assert "MEDIA:/absolute/local/path" in platform["platform_hint"]
    assert "Do not write MEDIA:https://" in platform["platform_hint"]


def test_plugin_platform_check_only_verifies_dependencies(monkeypatch):
    module = _load_plugin_module()
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(
        module,
        "_install_gateway",
        lambda: (_ for _ in ()).throw(AssertionError("installer should not run")),
    )
    monkeypatch.setattr(module, "_configure_runtime_defaults", lambda: None, raising=False)
    monkeypatch.setattr(module, "_clawchat_dependencies_available", lambda: True)
    monkeypatch.setattr(
        module,
        "_clawchat_connection_configured",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("check_fn should not validate credentials")
        ),
    )
    ctx = _PlatformCtx()

    module.register(ctx)

    assert ctx.platforms["clawchat"]["check_fn"]() is True


def test_plugin_platform_validation_falls_back_to_home_config(monkeypatch, tmp_path):
    module = _load_plugin_module()
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / ".env").write_text("CLAWCHAT_TOKEN=tok\n", encoding="utf-8")
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "platforms": {
                    "clawchat": {
                        "enabled": True,
                        "extra": {"websocket_url": "wss://home.example/ws"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(
        module,
        "_install_gateway",
        lambda: (_ for _ in ()).throw(AssertionError("installer should not run")),
    )
    monkeypatch.setattr(module, "_configure_runtime_defaults", lambda: None, raising=False)
    ctx = _PlatformCtx()

    module.register(ctx)

    platform_config = SimpleNamespace(extra={})
    assert ctx.platforms["clawchat"]["validate_config"](platform_config) is True


def test_plugin_adapter_factory_merges_home_config(monkeypatch, tmp_path):
    module = _load_plugin_module()
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / ".env").write_text("CLAWCHAT_TOKEN=tok\n", encoding="utf-8")
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "platforms": {
                    "clawchat": {
                        "enabled": True,
                        "extra": {
                            "websocket_url": "wss://home.example/ws",
                            "base_url": "https://home.example",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(
        module,
        "_install_gateway",
        lambda: (_ for _ in ()).throw(AssertionError("installer should not run")),
    )
    monkeypatch.setattr(module, "_configure_runtime_defaults", lambda: None, raising=False)
    ctx = _PlatformCtx()

    module.register(ctx)

    adapter = ctx.platforms["clawchat"]["adapter_factory"](SimpleNamespace(extra={}))
    assert adapter._clawchat_config.websocket_url == "wss://home.example/ws"
    assert adapter._clawchat_config.base_url == "https://home.example"


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


def test_plugin_tool_descriptions_forbid_execute_fallbacks(monkeypatch):
    module = _load_plugin_module()
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(module, "_install_gateway", lambda: None)
    ctx = _Ctx()

    module.register(ctx)

    for tool in ctx.tools.values():
        assert "Do not use execute" in tool["schema"]["description"]


def test_upload_media_tool_description_is_render_url_not_current_chat_delivery(monkeypatch):
    module = _load_plugin_module()
    monkeypatch.setattr(module, "_register_python_path", lambda _src: None)
    monkeypatch.setattr(module, "_install_gateway", lambda: None)
    ctx = _Ctx()

    module.register(ctx)

    description = ctx.tools["clawchat_upload_media_file"]["schema"]["description"]
    assert "media URL used by message fragments to render" in description
    assert "shareable" not in description
    assert "Do not use this tool to send an attachment in the current chat" in description
    assert "MEDIA:/absolute/local/path" in description


def test_clawchat_skill_uses_plugin_tools_not_shell_commands():
    skill = (Path(__file__).resolve().parents[1] / "skills" / "clawchat" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "Do not use execute" in skill
    assert "clawchat_list_account_friends" in skill
    assert '"$PY"' not in skill
    assert "python -" not in skill
    assert "-m clawchat_gateway" not in skill


def test_clawchat_skill_does_not_describe_media_upload_or_message_delivery():
    skill = (Path(__file__).resolve().parents[1] / "skills" / "clawchat" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "Send Media In Current Chat" not in skill
    assert "Media Upload" not in skill
    assert "clawchat_upload_media_file" not in skill
    assert "MEDIA:/absolute/local/path" not in skill
    assert "media rendering URL for message fragments" not in skill


def test_plugin_tool_handlers_return_json_strings_for_hermes_v012(monkeypatch):
    module = _load_plugin_module()

    from clawchat_gateway import tools

    async def fake_get_account_profile():
        return {"ok": True, "nickname": "测试账号"}

    monkeypatch.setattr(tools, "get_account_profile", fake_get_account_profile)

    result = asyncio.run(module._handle_clawchat_get_account_profile({}, task_id="trace-123"))

    assert isinstance(result, str)
    assert "测试账号" in result
    assert json.loads(result) == {"ok": True, "nickname": "测试账号"}


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
    payload = json.loads(result)

    assert payload["error"] == "validation"
    assert "absolute local path" in payload["message"]
