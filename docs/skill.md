# Skill — `skills/clawchat/SKILL.md`

A Hermes skill installed into `$HERMES_HOME/skills/clawchat/` by `install.install_skill()` and registered with Hermes via `ctx.register_skill("clawchat", skill, description=...)` in the repo-root `register()`. The skill text is surfaced verbatim to the Hermes LLM whenever the `clawchat` skill is activated.

## Frontmatter

```yaml
name: clawchat
description: Activate and operate the ClawChat Hermes gateway integration.
  Use when the user asks to configure ClawChat, says they have a ClawChat
  activation code, or asks whether ClawChat is connected.
version: 1.0.0
metadata:
  hermes:
    tags: [clawchat, gateway, activation, messaging]
```

## Content sections

The skill body encodes these flows (full text lives in `skills/clawchat/SKILL.md`; this doc summarises what each section instructs the model to do):

| Section | What the LLM is told to do |
|---|---|
| **Hermes Python** | Resolve a Python binary in priority order: `HERMES_PYTHON` env → `$HERMES_DIR/.venv/bin/python` → `~/.hermes/hermes-agent/.venv/bin/python` → `/opt/hermes/.venv/bin/python` → `python3`. All subsequent commands must use `$PY`, not system Python. |
| **Activation Flow** | If the user provided a code, run `"$PY" -m clawchat_gateway.activate CODE`. After success, restart Hermes (ordered fallbacks: `$HERMES_DIR/.venv/bin/hermes gateway restart` → `~/.hermes/hermes-agent/.venv/bin/hermes gateway restart` → `/opt/hermes/.venv/bin/hermes gateway restart` with `HERMES_HOME=/opt/data` → `hermes gateway restart`). Report success or "activation succeeded but restart must be done manually". |
| **Update Nickname** | Trigger phrases: 你叫…, 把 ClawChat 昵称改成…, change your name to…, update nickname to… Run `"$PY" -m clawchat_gateway.profile nickname "NEW_NICKNAME"`. If the command fails because ClawChat isn't activated, ask for the activation code first. |
| **Update Avatar** | Requires an absolute local path. If the user sent an image through ClawChat, use the downloaded local media path from the ClawChat runtime. Run `"$PY" -m clawchat_gateway.profile avatar "/absolute/path/..."`. The command itself enforces upload-first, then profile-update. |
| **Defaults** | Default API: `http://company.newbaselab.com:10086`. Default WebSocket: `ws://company.newbaselab.com:10086/ws`. Do not call `connect-codes`; activation uses `/v1/agents/connect`. |
| **Useful Checks** | Inspect current ClawChat config by loading `$HERMES_HOME/config.yaml` and printing `platforms.clawchat`. Tail `~/.hermes/logs/agent.log` (or `docker logs --since 10m hermes`) with `grep -i clawchat` to diagnose connection state. |

## Consistency contract

Both the tool `description` strings (in the repo-root `__init__.py::_register_tools`) and this SKILL.md are surfaced to the LLM. When editing one:

- Keep trigger-phrase examples aligned so the activation tool is picked up consistently.
- Keep the "upload-first, then profile" sequence for avatar updates identical in both places.
- Keep `/v1/agents/connect` as the only mentioned activation endpoint (not `connect-codes`).

## Installation

- Source: `skills/clawchat/` inside the repo, computed by `install._skill_source_dir()`.
- Target: `$HERMES_HOME/skills/clawchat/`, computed by `install._skill_target_dir()`.
- `install.install_skill(hermes_dir)` deletes any legacy `$HERMES_HOME/plugins/clawchat-tools/` directory and any existing target, then `shutil.copytree(source, target)`.
- `install.configure_clawchat_streaming()` additionally clears `$HERMES_HOME/.skills_prompt_snapshot.json` so Hermes regenerates the prompt snapshot on next boot.
