"""Anchor-patch installer for integrating ClawChat into hermes-agent."""

from __future__ import annotations

import argparse
import shutil
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class Patch:
    id: str
    file: str
    anchor: str
    payload: str
    insert_after: bool = True
    soft_fail: bool = False
    indent_to_anchor: bool = False


def _marker_start(pid: str) -> str:
    return f"# clawchat-gateway:{pid}:start"


def _marker_end(pid: str) -> str:
    return f"# clawchat-gateway:{pid}:end"


def patch_applied(patch: Patch) -> bool:
    try:
        text = Path(patch.file).read_text()
    except FileNotFoundError:
        return False
    return _marker_start(patch.id) in text


def _anchor_indent(line: str) -> str:
    match = re.match(r"[ \t]*", line)
    return match.group(0) if match else ""


def _format_payload(patch: Patch, anchor_line: str) -> str:
    payload = patch.payload
    if not payload.endswith("\n"):
        payload += "\n"
    if patch.indent_to_anchor:
        indent = _anchor_indent(anchor_line)
        payload = "".join(
            indent + line if line.strip() else line
            for line in payload.splitlines(keepends=True)
        )
    start = _marker_start(patch.id) + "\n"
    end = _marker_end(patch.id) + "\n"
    if patch.indent_to_anchor:
        indent = _anchor_indent(anchor_line)
        start = indent + start
        end = indent + end
    return start + payload + end


def apply_patch(patch: Patch) -> bool:
    path = Path(patch.file)
    try:
        text = path.read_text()
    except FileNotFoundError:
        return False
    if _marker_start(patch.id) in text:
        return False

    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if patch.anchor in line:
            insert_idx = index + 1 if patch.insert_after else index
            block = _format_payload(patch, line)
            path.write_text("".join(lines[:insert_idx] + [block] + lines[insert_idx:]))
            return True
    return False


def remove_patch(patch: Patch) -> bool:
    path = Path(patch.file)
    try:
        text = path.read_text()
    except FileNotFoundError:
        return False

    start = _marker_start(patch.id)
    end = _marker_end(patch.id)
    if start not in text:
        return False

    pattern = re.compile(
        rf"^[ \t]*{re.escape(start)}\n.*?^[ \t]*{re.escape(end)}\n",
        flags=re.DOTALL | re.MULTILINE,
    )
    new_text, count = pattern.subn("", text)
    if count == 0:
        return False
    path.write_text(new_text)
    return True


def build_patches(hermes_dir: Path) -> List[Patch]:
    cfg = str(hermes_dir / "gateway" / "config.py")
    run = str(hermes_dir / "gateway" / "run.py")
    prompts = str(hermes_dir / "agent" / "prompt_builder.py")
    send_tool = str(hermes_dir / "tools" / "send_message_tool.py")
    cli_platforms = str(hermes_dir / "hermes_cli" / "platforms.py")
    cron_scheduler = str(hermes_dir / "cron" / "scheduler.py")

    return [
        Patch(
            id="platform_enum",
            file=cfg,
            anchor='QQBOT = "qqbot"',
            payload='CLAWCHAT = "clawchat"\n',
            insert_after=True,
            indent_to_anchor=True,
        ),
        Patch(
            id="env_overrides",
            file=cfg,
            anchor="# Session settings",
            payload=(
                "# ClawChat env overrides\n"
                'clawchat_websocket_url = os.getenv("CLAWCHAT_WEBSOCKET_URL", "").strip() or os.getenv("CLAWCHAT_WS_URL", "").strip()\n'
                'clawchat_base_url = os.getenv("CLAWCHAT_BASE_URL", "").strip()\n'
                'clawchat_token = os.getenv("CLAWCHAT_TOKEN", "").strip()\n'
                'clawchat_user_id = os.getenv("CLAWCHAT_USER_ID", "").strip()\n'
                'clawchat_reply_mode = os.getenv("CLAWCHAT_REPLY_MODE", "").strip()\n'
                'clawchat_group_mode = os.getenv("CLAWCHAT_GROUP_MODE", "").strip()\n'
                'clawchat_media_roots = os.getenv("CLAWCHAT_MEDIA_LOCAL_ROOTS", "").strip()\n'
                "if clawchat_websocket_url or clawchat_token:\n"
                "    if Platform.CLAWCHAT not in config.platforms:\n"
                "        config.platforms[Platform.CLAWCHAT] = PlatformConfig()\n"
                "    config.platforms[Platform.CLAWCHAT].enabled = True\n"
                "    _ce = config.platforms[Platform.CLAWCHAT].extra\n"
                '    if clawchat_websocket_url: _ce["websocket_url"] = clawchat_websocket_url\n'
                '    if clawchat_base_url: _ce["base_url"] = clawchat_base_url\n'
                '    if clawchat_token: _ce["token"] = clawchat_token\n'
                '    if clawchat_user_id: _ce["user_id"] = clawchat_user_id\n'
                '    if clawchat_reply_mode: _ce["reply_mode"] = clawchat_reply_mode\n'
                '    if clawchat_group_mode: _ce["group_mode"] = clawchat_group_mode\n'
                '    if clawchat_media_roots:\n'
                '        _ce["media_local_roots"] = [p.strip() for p in clawchat_media_roots.split(os.pathsep) if p.strip()]\n'
            ),
            insert_after=False,
            indent_to_anchor=True,
        ),
        Patch(
            id="connected_platforms",
            file=cfg,
            anchor='elif platform == Platform.QQBOT and config.extra.get("app_id") and config.extra.get("client_secret"):',
            payload=(
                'elif platform == Platform.CLAWCHAT and config.extra.get("websocket_url") and config.extra.get("token"):\n'
                "    connected.append(platform)\n"
            ),
            insert_after=False,
            indent_to_anchor=True,
        ),
        Patch(
            id="adapter_factory",
            file=run,
            anchor="elif platform == Platform.QQBOT:",
            payload=(
                "elif platform == Platform.CLAWCHAT:\n"
                "    from clawchat_gateway.adapter import ClawChatAdapter, check_clawchat_requirements\n"
                "    if not check_clawchat_requirements(config):\n"
                '        logger.warning("ClawChat: websocket_url/token missing or websockets not installed")\n'
                "        return None\n"
                "    return ClawChatAdapter(config)\n"
            ),
            insert_after=False,
            indent_to_anchor=True,
        ),
        Patch(
            id="auth_maps_allowed",
            file=run,
            anchor='Platform.QQBOT: "QQ_ALLOWED_USERS",',
            payload='Platform.CLAWCHAT: "CLAWCHAT_ALLOWED_USERS",\n',
            insert_after=True,
            indent_to_anchor=True,
        ),
        Patch(
            id="auth_maps_allow_all",
            file=run,
            anchor='Platform.QQBOT: "QQ_ALLOW_ALL_USERS",',
            payload='Platform.CLAWCHAT: "CLAWCHAT_ALLOW_ALL_USERS",\n',
            insert_after=True,
            indent_to_anchor=True,
        ),
        Patch(
            id="prompt_hints",
            file=prompts,
            anchor='"qqbot": (',
            payload=(
                '"clawchat": (\n'
                '    "You are on ClawChat, a chat platform with structured text and media fragments. "\n'
                '    "Keep replies compact and chat-native. You can send media files natively: "\n'
                '    "include MEDIA:/absolute/path/to/file in your response. Images, audio, video, "\n'
                '    "and files are emitted as native ClawChat fragments."\n'
                "),\n"
            ),
            insert_after=False,
            indent_to_anchor=True,
        ),
        Patch(
            id="post_stream_hook",
            file=run,
            anchor="await asyncio.wait_for(stream_task, timeout=5.0)",
            payload=(
                "_ca = self.adapters.get(source.platform) if hasattr(self, 'adapters') else None\n"
                "if _ca is not None and hasattr(_ca, 'on_run_complete'):\n"
                "    try:\n"
                "        await _ca.on_run_complete(source.chat_id, full_response)\n"
                "    except Exception:\n"
                "        logger.exception('clawchat on_run_complete failed')\n"
            ),
            insert_after=True,
            indent_to_anchor=True,
            soft_fail=True,
        ),
        Patch(
            id="normal_stream_done_hook",
            file=run,
            anchor="# Clean up tracking",
            payload=(
                "_ca = self.adapters.get(source.platform) if hasattr(self, 'adapters') else None\n"
                "if _ca is not None and hasattr(_ca, 'on_run_complete'):\n"
                "    try:\n"
                "        _result = result_holder[0] or {}\n"
                "        _full_response = _result.get('final_response', '') if isinstance(_result, dict) else ''\n"
                "        await _ca.on_run_complete(source.chat_id, _full_response)\n"
                "    except Exception:\n"
                "        logger.exception('clawchat on_run_complete failed')\n"
            ),
            insert_after=False,
            indent_to_anchor=True,
            soft_fail=True,
        ),
        Patch(
            id="send_message_tool",
            file=send_tool,
            anchor='"qqbot": Platform.QQBOT,',
            payload='"clawchat": Platform.CLAWCHAT,\n',
            insert_after=True,
            indent_to_anchor=True,
        ),
        Patch(
            id="cli_platform_registry",
            file=cli_platforms,
            anchor='("qqbot",',
            payload='("clawchat",       PlatformInfo(label="ClawChat",         default_toolset="hermes-cli")),\n',
            insert_after=True,
            indent_to_anchor=True,
        ),
        Patch(
            id="cron_known_delivery_platforms",
            file=cron_scheduler,
            anchor='"qqbot",',
            payload='"clawchat",\n',
            insert_after=True,
            indent_to_anchor=True,
        ),
        Patch(
            id="cron_platform_map",
            file=cron_scheduler,
            anchor='"qqbot": Platform.QQBOT,',
            payload='"clawchat": Platform.CLAWCHAT,\n',
            insert_after=True,
            indent_to_anchor=True,
        ),
        Patch(
            id="startup_any_allowlist",
            file=run,
            anchor='"QQ_ALLOWED_USERS",',
            payload='"CLAWCHAT_ALLOWED_USERS",\n',
            insert_after=True,
            indent_to_anchor=True,
        ),
        Patch(
            id="startup_allow_all",
            file=run,
            anchor='"QQ_ALLOW_ALL_USERS")',
            payload='"CLAWCHAT_ALLOW_ALL_USERS", ',
            insert_after=False,
            indent_to_anchor=False,
            soft_fail=True,
        ),
        Patch(
            id="startup_allow_all_yuanbao",
            file=run,
            anchor='"YUANBAO_ALLOW_ALL_USERS")',
            payload='"CLAWCHAT_ALLOW_ALL_USERS",\n',
            insert_after=False,
            indent_to_anchor=True,
            soft_fail=True,
        ),
        Patch(
            id="update_allowed_platforms",
            file=run,
            anchor="Platform.FEISHU, Platform.WECOM, Platform.WECOM_CALLBACK, Platform.WEIXIN, Platform.BLUEBUBBLES, Platform.QQBOT, Platform.LOCAL,",
            payload="Platform.CLAWCHAT, ",
            insert_after=False,
            indent_to_anchor=False,
        ),
    ]


def _state_file(hermes_dir: Path) -> Path:
    return hermes_dir / ".clawchat_gateway_install_state.json"


def _skill_source_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "skills" / "clawchat"


def _skill_target_dir(hermes_dir: Path) -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    return hermes_home / "skills" / "clawchat"


def _legacy_plugin_target_dir(hermes_dir: Path) -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    return hermes_home / "plugins" / "clawchat-tools"


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def _env_file() -> Path:
    return _hermes_home() / ".env"


def configure_clawchat_allow_all() -> bool:
    """Allow ClawChat users by default without opening every gateway platform."""
    env_path = _env_file()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    changed = False
    found = False

    for idx, line in enumerate(lines):
        if line.startswith("CLAWCHAT_ALLOW_ALL_USERS="):
            found = True
            if line != "CLAWCHAT_ALLOW_ALL_USERS=true":
                lines[idx] = "CLAWCHAT_ALLOW_ALL_USERS=true"
                changed = True
            break

    if not found:
        lines.append("CLAWCHAT_ALLOW_ALL_USERS=true")
        changed = True

    if changed:
        env_path.write_text("\n".join(lines) + "\n")
    return changed


def configure_clawchat_streaming() -> bool:
    config_path = _hermes_home() / "config.yaml"
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text()) or {}
        except Exception:
            config = {}
    else:
        config = {}

    changed = False
    platforms = config.setdefault("platforms", {})
    clawchat = platforms.setdefault("clawchat", {})
    extra = clawchat.setdefault("extra", {})
    if extra.get("reply_mode") != "stream":
        extra["reply_mode"] = "stream"
        changed = True
    for key in ("show_tools_output", "show_think_output"):
        if extra.get(key) is not False:
            extra[key] = False
            changed = True

    streaming = config.setdefault("streaming", {})
    stream_defaults = {
        "enabled": True,
        "transport": "edit",
        "edit_interval": 0.25,
        "buffer_threshold": 16,
    }
    for key, value in stream_defaults.items():
        if streaming.get(key) != value:
            streaming[key] = value
            changed = True

    display = config.setdefault("display", {})
    display_platforms = display.setdefault("platforms", {})
    clawchat_display = display_platforms.setdefault("clawchat", {})
    display_defaults = {
        "tool_progress": "off",
        "show_reasoning": False,
    }
    for key, value in display_defaults.items():
        if clawchat_display.get(key) != value:
            clawchat_display[key] = value
            changed = True

    if changed:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(config, allow_unicode=False, sort_keys=False))
    return changed


def clear_skills_prompt_snapshot() -> bool:
    snapshot = _hermes_home() / ".skills_prompt_snapshot.json"
    if not snapshot.exists():
        return False
    snapshot.unlink()
    return True


def install_skill(hermes_dir: Path) -> bool:
    source = _skill_source_dir()
    target = _skill_target_dir(hermes_dir)
    if not source.is_dir():
        return False
    legacy_plugin = _legacy_plugin_target_dir(hermes_dir)
    if legacy_plugin.exists():
        shutil.rmtree(legacy_plugin)
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return True


def uninstall_skill(hermes_dir: Path) -> bool:
    target = _skill_target_dir(hermes_dir)
    if not target.exists():
        return False
    shutil.rmtree(target)
    return True


def skill_installed(hermes_dir: Path) -> bool:
    target = _skill_target_dir(hermes_dir)
    return (target / "SKILL.md").exists()


install_plugin = install_skill
uninstall_plugin = uninstall_skill
plugin_installed = skill_installed


def _write_state(hermes_dir: Path, applied: List[str]) -> None:
    _state_file(hermes_dir).write_text(
        json.dumps(
            {
                "clawchat_gateway_version": "0.1.0",
                "installed_at": datetime.now(timezone.utc).isoformat(),
                "patches_applied": applied,
            },
            indent=2,
        )
    )


def _read_state(hermes_dir: Path) -> Optional[dict]:
    state_path = _state_file(hermes_dir)
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text())
    except (OSError, ValueError):
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="clawchat-gateway-install")
    parser.add_argument(
        "--hermes-dir",
        default=os.environ.get(
            "HERMES_AGENT_DIR", str(Path.home() / ".hermes" / "hermes-agent")
        ),
    )
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    hermes_dir = Path(args.hermes_dir)
    if not hermes_dir.is_dir():
        print(f"error: hermes-dir does not exist: {hermes_dir}", file=sys.stderr)
        return 2

    patches = build_patches(hermes_dir)

    if args.check:
        applied = [patch.id for patch in patches if patch_applied(patch)]
        missing = [patch.id for patch in patches if patch.id not in applied]
        print(
            json.dumps(
                {
                    "installed": len(missing) == 0 and skill_installed(hermes_dir),
                    "applied": applied,
                    "missing": missing,
                    "skill_installed": skill_installed(hermes_dir),
                    "state": _read_state(hermes_dir),
                },
                indent=2,
            )
        )
        return 0 if not missing and skill_installed(hermes_dir) else 1

    if args.uninstall:
        changed = []
        for patch in reversed(patches):
            if args.dry_run:
                if patch_applied(patch):
                    changed.append(patch.id)
                continue
            if remove_patch(patch):
                changed.append(patch.id)
        if not args.dry_run:
            try:
                _state_file(hermes_dir).unlink(missing_ok=True)
            except TypeError:
                state_path = _state_file(hermes_dir)
                if state_path.exists():
                    state_path.unlink()
            uninstall_skill(hermes_dir)
        print(json.dumps({"removed": changed}, indent=2))
        return 0

    applied: List[str] = []
    missing: List[str] = []
    newly_applied: List[Patch] = []
    for patch in patches:
        if args.dry_run:
            if patch_applied(patch):
                continue
            path = Path(patch.file)
            if not path.exists():
                if patch.soft_fail:
                    continue
                missing.append(patch.id)
                continue
            text = path.read_text()
            if patch.anchor not in text:
                if patch.soft_fail:
                    continue
                missing.append(patch.id)
                continue
            applied.append(patch.id)
            continue

        result = apply_patch(patch)
        if result:
            applied.append(patch.id)
            newly_applied.append(patch)
            continue
        if patch_applied(patch):
            continue
        if patch.soft_fail:
            continue
        missing.append(patch.id)

    if missing:
        rolled_back: List[str] = []
        if not args.dry_run:
            for patch in reversed(newly_applied):
                if remove_patch(patch):
                    rolled_back.append(patch.id)
        print(
            json.dumps(
                {
                    "error": "failed_to_apply_some_patches",
                    "applied": applied,
                    "missing": missing,
                    "rolled_back": rolled_back,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    if not args.dry_run:
        if not install_skill(hermes_dir):
            print(
                json.dumps(
                    {
                        "error": "failed_to_install_skill",
                        "skill_source": str(_skill_source_dir()),
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 1
        allow_all_changed = configure_clawchat_allow_all()
        streaming_changed = configure_clawchat_streaming()
        skills_snapshot_cleared = clear_skills_prompt_snapshot()
        _write_state(hermes_dir, [patch.id for patch in patches if patch_applied(patch)])
    else:
        allow_all_changed = False
        streaming_changed = False
        skills_snapshot_cleared = False

    print(
        json.dumps(
            {
                "applied": applied,
                "dry_run": args.dry_run,
                "skill_installed": False if args.dry_run else skill_installed(hermes_dir),
                "clawchat_allow_all_configured": False if args.dry_run else True,
                "clawchat_allow_all_changed": allow_all_changed,
                "clawchat_streaming_configured": False if args.dry_run else True,
                "clawchat_streaming_changed": streaming_changed,
                "skills_snapshot_cleared": skills_snapshot_cleared,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
