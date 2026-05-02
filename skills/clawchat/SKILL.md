---
name: clawchat
description: Activate and operate the ClawChat Hermes gateway integration with the registered ClawChat plugin tools. Use when the user asks to activate ClawChat, manage the connected ClawChat account, inspect ClawChat contacts, or upload ClawChat media.
version: 1.1.0
metadata:
  hermes:
    tags: [clawchat, gateway, activation, messaging, tools]
---

# ClawChat Gateway

You are running inside Hermes with ClawChat plugin tools already registered. For ClawChat account, contact, activation, profile, avatar, and media operations, call the registered `clawchat_*` plugin tools directly.

Do not use execute, shell scripts, Python snippets, curl, or direct HTTP requests to perform these ClawChat API actions. Do not read ClawChat tokens from files or environment variables yourself. The plugin tools own credential lookup, validation, API calls, uploads, config writes, and restart scheduling.

If a matching `clawchat_*` tool is unavailable, say that the ClawChat plugin tool is unavailable instead of falling back to `execute`.

## Activation

Use `clawchat_activate` when the user provides a ClawChat activation code or asks to activate/bind ClawChat.

Extract the code verbatim. Examples:

- `clawchat 的激活码是 R4E1IW` -> `R4E1IW`
- `ClawChat激活码: R4E1IW` -> `R4E1IW`
- `激活 clawchat R4E1IW` -> `R4E1IW`

After `clawchat_activate` succeeds, tell the user ClawChat activation is complete and the Hermes gateway restart has been scheduled in the background. Do not run a separate gateway restart command.

## Account Profile

Use `clawchat_get_account_profile` when the user asks for the connected ClawChat account profile, nickname, avatar, bio, user id, or current configured account.

Use `clawchat_update_account_profile` when the user explicitly asks to update the connected ClawChat account:

- For nickname/name changes, pass `nickname`.
- For bio/self-introduction changes, pass `bio`.
- For avatar URL changes, pass `avatar_url`.
- You may pass more than one field when the user asks for multiple profile changes together.

Do not use these tools for the Hermes/OpenClaw agent persona unless the user explicitly means the ClawChat account profile.

## User Profile

Use `clawchat_get_user_profile` only when the user provides a concrete ClawChat `userId` and asks to inspect that user's public profile.

Do not infer a `userId` from a nickname or display name. If the user did not provide a `userId`, ask for it.

## Friends

Use `clawchat_list_account_friends` when the user asks for the connected ClawChat account's friends, contacts, friend list, or a paginated friend/contact view.

Default to `page=1` and `pageSize=20` unless the user asks for a specific page or size.

## Avatar Upload

Use `clawchat_upload_avatar_image` when the user provides an absolute local image path and asks to upload it for use as the ClawChat account avatar.

This upload tool returns a hosted avatar URL and does not update the account profile by itself. If the user asked to set the avatar, call `clawchat_update_account_profile` with the returned `avatar_url` after upload succeeds.

If the user sent an image through ClawChat, use the local media path exposed by the ClawChat runtime. If no local path is available, ask for an absolute local image path.

## Media Upload

Use `clawchat_upload_media_file` when the user provides an absolute local file path and asks to upload, share, or create a ClawChat-accessible link for that file.

Do not use `clawchat_upload_media_file` for account avatars; use `clawchat_upload_avatar_image` for avatar image uploads.

## Response Style

Report the result briefly in chat-native language. Include useful returned identifiers, URLs, nicknames, or counts when the tool returns them. If a tool returns an error, explain the error and the missing input or failing condition without trying an alternate shell/API path.
