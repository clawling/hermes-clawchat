# Skill — `skills/clawchat/SKILL.md`

A Hermes skill installed into `$HERMES_HOME/skills/clawchat/` by `install.install_skill()` and registered with Hermes via `ctx.register_skill("clawchat", skill, description=...)` in the repo-root `register()`. The skill text is surfaced verbatim to the Hermes LLM whenever the `clawchat` skill is activated.

## Frontmatter

```yaml
name: clawchat
description: Activate and operate the ClawChat Hermes gateway integration with
  the registered ClawChat plugin tools. Use when the user asks to activate
  ClawChat, manage the connected ClawChat account, or inspect ClawChat contacts.
version: 1.1.0
metadata:
  hermes:
    tags: [clawchat, gateway, activation, messaging, tools]
```

## Content sections

The skill body encodes these flows (full text lives in `skills/clawchat/SKILL.md`; this doc summarises what each section instructs the model to do):

| Section | What the LLM is told to do |
|---|---|
| **Tool boundary** | For ClawChat API operations, call the registered `clawchat_*` plugin tools directly. Do not fall back to `execute`, scripts, direct HTTP calls, or manual token reads. If a matching tool is unavailable, report that instead of inventing a shell path. |
| **Activation** | If the user provides a code, call `clawchat_activate` with the verbatim code. After success, report that activation is complete and the gateway restart has been scheduled in the background. Do not run a separate gateway restart command. |
| **Account Profile** | Use `clawchat_get_account_profile` for the connected account, and `clawchat_update_account_profile` for explicit nickname, avatar URL, or bio changes. |
| **User Profile** | Use `clawchat_get_user_profile` only when the user provides a concrete ClawChat `userId`; ask for the id instead of guessing. |
| **Friends** | Use `clawchat_list_account_friends` for friends/contacts queries, defaulting to `page=1` and `pageSize=20` unless specified. |
| **Avatar Upload** | Use `clawchat_upload_avatar_image` for an absolute local image path. If the user wants to set the avatar, follow with `clawchat_update_account_profile` using the returned `avatar_url`. |

## Consistency contract

Both the tool `description` strings (in the repo-root `__init__.py::_register_tools`) and this SKILL.md are surfaced to the LLM. When editing one:

- Keep trigger-phrase examples aligned so the activation tool is picked up consistently.
- Keep the "upload-first, then profile" sequence for avatar updates identical in both places.
- Keep the direct-tool boundary explicit so Hermes does not choose the generic `execute` tool for ClawChat API operations.

## Installation

- Source: `skills/clawchat/` inside the repo, computed by `install._skill_source_dir()`.
- Target: `$HERMES_HOME/skills/clawchat/`, computed by `install._skill_target_dir()`.
- `install.install_skill(hermes_dir)` deletes any legacy `$HERMES_HOME/plugins/clawchat-tools/` directory and any existing target, then `shutil.copytree(source, target)`.
- `install.configure_clawchat_streaming()` additionally clears `$HERMES_HOME/.skills_prompt_snapshot.json` so Hermes regenerates the prompt snapshot on next boot.
