from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clawchat_gateway.config import ClawChatConfig


@dataclass(frozen=True)
class InboundMessage:
    chat_id: str
    chat_type: str
    sender_id: str
    sender_name: str
    text: str
    raw_message: dict[str, Any]
    reply_preview: dict[str, Any] | None = None
    media_urls: list[str] = field(default_factory=list)


def parse_inbound_message(
    envelope: dict[str, Any], config: ClawChatConfig
) -> InboundMessage | None:
    payload = envelope.get("payload") or {}
    message = payload.get("message") or {}
    context = message.get("context") or {}
    chat_type = envelope.get("chat_type") or "direct"

    if chat_type == "group" and config.group_mode == "mention":
        mentions = context.get("mentions") or []
        if not any(
            mention.get("id") == config.user_id
            for mention in mentions
            if isinstance(mention, dict)
        ):
            return None

    fragments = message.get("fragments") or []
    text_parts: list[str] = []
    media_urls: list[str] = []

    for fragment in fragments:
        if not isinstance(fragment, dict):
            continue
        kind = fragment.get("kind")
        if kind == "text" and isinstance(fragment.get("text"), str):
            text_parts.append(fragment["text"])
            continue
        if kind in {"image", "file", "audio", "video"} and isinstance(
            fragment.get("url"), str
        ):
            media_urls.append(fragment["url"])
            label = fragment.get("name") or fragment["url"]
            if kind == "image":
                text_parts.append(f"![{label}]({fragment['url']})")
            else:
                text_parts.append(f"[{label}]({fragment['url']})")

    sender = envelope.get("sender") or {}
    return InboundMessage(
        chat_id=envelope.get("chat_id") or "",
        chat_type=chat_type,
        sender_id=sender.get("id") or "",
        sender_name=sender.get("nick_name") or "",
        text="\n".join(part for part in text_parts if part),
        raw_message=envelope,
        reply_preview=context.get("reply"),
        media_urls=media_urls,
    )
