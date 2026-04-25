# Installer — `src/clawchat_gateway/install.py`

Anchor-patch based installer for integrating ClawChat into hermes-agent. Also copies `skills/clawchat/` into `$HERMES_HOME/skills/clawchat/`, seeds streaming defaults in `config.yaml`, and sets `CLAWCHAT_ALLOW_ALL_USERS=true` in `$HERMES_HOME/.env`.

Exposed as:
- Python: `from clawchat_gateway.install import main; main([...])`
- Module: `python -m clawchat_gateway.install`
- Console script: `clawchat-gateway-install` (per `pyproject.toml`)

## Dataclasses

### `Patch`

```python
@dataclass
class Patch:
    id: str
    file: str
    anchor: str
    payload: str
    insert_after: bool = True
    soft_fail: bool = False
    indent_to_anchor: bool = False
```

- `id` — unique name used to build start/end markers (`# clawchat-gateway:<id>:start`).
- `file` — absolute path to a hermes-agent source file.
- `anchor` — substring searched line-by-line; first match wins.
- `payload` — text to insert (newline-terminated internally).
- `insert_after` — `True` inserts after the anchor line, `False` inserts before.
- `soft_fail` — when `True`, missing file or missing anchor is not an error (used for hooks whose insertion site may not exist in older hermes-agent builds).
- `indent_to_anchor` — when `True`, every non-blank payload line and both markers are prefixed with the anchor line's leading whitespace.

## Marker helpers

| Function | Signature | Purpose |
|---|---|---|
| `_marker_start` | `(pid: str) -> str` | Return `# clawchat-gateway:{pid}:start`. |
| `_marker_end` | `(pid: str) -> str` | Return `# clawchat-gateway:{pid}:end`. |
| `patch_applied` | `(patch: Patch) -> bool` | True iff the file exists and already contains the start marker. |
| `_anchor_indent` | `(line: str) -> str` | Leading tabs/spaces of a line (via regex `[ \t]*`). |
| `_format_payload` | `(patch, anchor_line) -> str` | Produce the full block: start marker, payload (optionally indented), end marker. |

## Patch apply / remove

| Function | Signature | Behaviour |
|---|---|---|
| `apply_patch` | `(patch: Patch) -> bool` | Returns `True` if a new block was inserted. `False` if the file is missing, the start marker is already present, or the anchor was not found. Writes the file back in place. |
| `remove_patch` | `(patch: Patch) -> bool` | Strips the start…end block (DOTALL, MULTILINE, allowing leading indent). Returns `False` if the file or marker is missing. |

## The patch set — `build_patches(hermes_dir: Path) -> list[Patch]`

Returns the full list of patches, targeting files under `hermes_dir`:

| id | target file | anchor (substring) | payload (summary) |
|---|---|---|---|
| `platform_enum` | `gateway/config.py` | `QQBOT = "qqbot"` | `CLAWCHAT = "clawchat"` |
| `env_overrides` | `gateway/config.py` | `# Session settings` | `CLAWCHAT_*` env vars → `platforms.clawchat.extra` |
| `connected_platforms` | `gateway/config.py` | `elif platform == Platform.QQBOT and config.extra.get("app_id") ...` | Gate on `websocket_url` + `token` |
| `adapter_factory` | `gateway/run.py` | `elif platform == Platform.QQBOT:` | Import + return `ClawChatAdapter(config)` |
| `auth_maps_allowed` | `gateway/run.py` | `Platform.QQBOT: "QQ_ALLOWED_USERS",` | `Platform.CLAWCHAT: "CLAWCHAT_ALLOWED_USERS",` |
| `auth_maps_allow_all` | `gateway/run.py` | `Platform.QQBOT: "QQ_ALLOW_ALL_USERS",` | `Platform.CLAWCHAT: "CLAWCHAT_ALLOW_ALL_USERS",` |
| `prompt_hints` | `agent/prompt_builder.py` | `"qqbot": (` | Per-platform prompt hint for ClawChat (MEDIA:/abs/path instructions) |
| `post_stream_hook` | `gateway/run.py` | `await asyncio.wait_for(stream_task, timeout=5.0)` | Call `adapter.on_run_complete(chat_id, full_response)` — `soft_fail=True` |
| `normal_stream_done_hook` | `gateway/run.py` | `# Clean up tracking` | Call `adapter.on_run_complete` from `result_holder` — `soft_fail=True` |
| `send_message_tool` | `tools/send_message_tool.py` | `"qqbot": Platform.QQBOT,` | `"clawchat": Platform.CLAWCHAT,` |
| `cli_platform_registry` | `hermes_cli/platforms.py` | `("qqbot",` | `("clawchat", PlatformInfo(label="ClawChat", default_toolset="hermes-cli")),` |
| `cron_known_delivery_platforms` | `cron/scheduler.py` | `"qqbot",` | `"clawchat",` — adds ClawChat to the cron delivery allowlist |
| `cron_platform_map` | `cron/scheduler.py` | `"qqbot": Platform.QQBOT,` | `"clawchat": Platform.CLAWCHAT,` — maps `deliver=clawchat:<chat_id>` cron jobs to the platform enum |
| `startup_any_allowlist` | `gateway/run.py` | `"QQ_ALLOWED_USERS",` | `"CLAWCHAT_ALLOWED_USERS",` |
| `startup_allow_all` | `gateway/run.py` | `"QQ_ALLOW_ALL_USERS")` | `"CLAWCHAT_ALLOW_ALL_USERS", ` (inserted **before**, not indented) |
| `update_allowed_platforms` | `gateway/run.py` | `Platform.FEISHU, ... QQBOT, Platform.LOCAL,` | `Platform.CLAWCHAT, ` (inserted before, not indented) |

**Editing guidance.** If you change a patch payload, bump or re-scope the `id` (or uninstall + reinstall) so existing deployments don't skip your new content because the old start marker is already present.

## Supporting filesystem operations

| Function | Signature | Purpose |
|---|---|---|
| `_state_file` | `(hermes_dir: Path) -> Path` | `<hermes_dir>/.clawchat_gateway_install_state.json` |
| `_skill_source_dir` | `() -> Path` | `<repo>/skills/clawchat`, computed relative to this file. |
| `_skill_target_dir` | `(hermes_dir: Path) -> Path` | `$HERMES_HOME/skills/clawchat` |
| `_legacy_plugin_target_dir` | `(hermes_dir: Path) -> Path` | `$HERMES_HOME/plugins/clawchat-tools` — deleted on install for migration. |
| `_hermes_home` | `() -> Path` | `$HERMES_HOME` or `~/.hermes`. |
| `_env_file` | `() -> Path` | `$HERMES_HOME/.env`. |
| `configure_clawchat_allow_all` | `() -> bool` | Ensures `CLAWCHAT_ALLOW_ALL_USERS=true` is present in `$HERMES_HOME/.env`. Returns `True` if changed. |
| `configure_clawchat_streaming` | `() -> bool` | Writes/updates `~/.hermes/config.yaml`: `platforms.clawchat.extra.reply_mode=stream`, `show_tools_output=false`, `show_think_output=false`; `streaming` block (`enabled=true`, `transport=edit`, `edit_interval=0.25`, `buffer_threshold=16`); `display.platforms.clawchat.tool_progress=off`, `show_reasoning=false`. Returns `True` if changed. |
| `clear_skills_prompt_snapshot` | `() -> bool` | Remove `$HERMES_HOME/.skills_prompt_snapshot.json` so hermes regenerates prompt state next boot. |
| `install_skill` | `(hermes_dir: Path) -> bool` | Remove legacy plugin dir + existing target, then `shutil.copytree(source, target)`. Returns `False` if the source doesn't exist. |
| `uninstall_skill` | `(hermes_dir: Path) -> bool` | Remove target skill dir. |
| `skill_installed` | `(hermes_dir: Path) -> bool` | True if `<target>/SKILL.md` exists. |
| `install_plugin` / `uninstall_plugin` / `plugin_installed` | — | Aliases kept for backwards compat. |

## Install state

| Function | Signature | Purpose |
|---|---|---|
| `_write_state` | `(hermes_dir: Path, applied: list[str]) -> None` | JSON: `{clawchat_gateway_version, installed_at (ISO UTC), patches_applied}`. |
| `_read_state` | `(hermes_dir: Path) -> dict \| None` | Returns `None` if missing or malformed. |

## CLI — `main(argv=None) -> int`

Flags:
- `--hermes-dir` (default: `$HERMES_AGENT_DIR` or `~/.hermes/hermes-agent`).
- `--check` — print JSON status (`installed`, `applied`, `missing`, `skill_installed`, `state`). Exit 0 only if fully installed.
- `--uninstall` — remove patches in reverse order, delete state file, uninstall skill. Honours `--dry-run`.
- `--dry-run` — compute-only, print without writing.

### Atomic install

The non-dry-run install path tracks every newly applied patch in a `newly_applied` list. The moment a patch fails (anchor missing, file missing, and `soft_fail=False`), the runner walks `reversed(newly_applied)` and calls `remove_patch` on each, then prints

```json
{"error": "failed_to_apply_some_patches", "applied": [...], "missing": [...], "rolled_back": [...]}
```

to stderr and returns `1`. This guarantees hermes-agent never observes a half-patched tree (for example: `Platform.CLAWCHAT` referenced in `gateway/run.py` without the enum member having been added to `gateway/config.py`).

`tests/test_install.py::test_install_rolls_back_when_anchor_missing` exercises this path.

Exit codes:
- `0` — success / clean check.
- `1` — missing patches (after rollback), skill install failure, or incomplete check.
- `2` — `--hermes-dir` doesn't exist.

Install output JSON fields:
```
applied, dry_run, skill_installed,
clawchat_allow_all_configured, clawchat_allow_all_changed,
clawchat_streaming_configured, clawchat_streaming_changed,
skills_snapshot_cleared
```

Uninstall output JSON: `{"removed": [patch_id, ...]}`.
