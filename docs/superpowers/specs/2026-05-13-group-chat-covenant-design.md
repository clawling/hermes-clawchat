# Group Chat Covenant Design

## Goal

ClawChat group conversations should receive trusted runtime guidance that does not affect direct messages. The first version adds a default group covenant and changes the default group trigger policy from mention-only to all group messages.

Per-group custom prompts are out of scope for this iteration. Conversation metadata and members can be fetched later through `GET /conversations/{id}`.

## Decisions

- Use Hermes `MessageEvent.channel_prompt` for group-only prompt injection.
- Treat `channel_prompt` as an ephemeral system prompt path, not as a WebSocket protocol field and not as a plugin hook.
- Set `event.channel_prompt` only when `inbound.chat_type == "group"`.
- Keep direct messages free of group covenant text.
- Preserve existing activation behavior by appending the activation prompt and group covenant when both apply.
- Change `ClawChatConfig.group_mode` default from `"mention"` to `"all"`.
- Keep explicit `group_mode="mention"` support so installations can opt back into mention-only filtering.

## Prompt Shape

The default group covenant is loaded by a small prompt builder and rendered with a clear trusted-context label, for example:

```text
ClawChat group covenant:
<covenant text>
```

Tests will override the covenant text with:

```text
群里陈平安是落魄山共和国的国王。它的位置在卡拉米星球的洪荒大陆上。
```

That fixture text is not product default copy.

## Implementation Sketch

Add a focused group-context helper, likely `clawchat_gateway/group_context.py`, responsible for loading and formatting the default covenant. The adapter calls this helper while building a `MessageEvent` for inbound group messages.

The adapter remains responsible for:

- parsing inbound WebSocket frames into `InboundMessage`;
- mapping ClawChat chat types into Hermes `SessionSource`;
- composing `event.channel_prompt` from group covenant text and any existing activation prompt;
- dispatching the event through `handle_message`.

Config changes update the `ClawChatConfig` default and documentation. Existing env/config resolution continues to allow `CLAWCHAT_GROUP_MODE` or `platforms.clawchat.extra.group_mode` to override the default.

## Error Handling

If the covenant source is missing or empty, group messages should still dispatch normally with no covenant prompt. Loading failures should be logged at debug or warning level and must not drop the inbound message.

If future conversation-detail fetching fails, the fallback should still include the static group covenant when available.

## Testing

Add or update unit tests for:

- group inbound messages get `event.channel_prompt` containing the test covenant;
- direct inbound messages do not get a group covenant;
- activation-intent group messages append both the group covenant and activation prompt;
- `ClawChatConfig` defaults `group_mode` to `"all"`;
- explicit `group_mode="mention"` still filters unmentioned group messages.

Docs to update with implementation:

- `docs/config.md`
- `docs/adapter.md`
- `docs/inbound.md`
- `docs/architecture.md`
- `docs/tests.md`
- user-facing install/README docs if they mention the default group mode
