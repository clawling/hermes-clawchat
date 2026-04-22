"""ClawChatAdapter — BasePlatformAdapter for the ClawChat WebSocket protocol."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from gateway.config import Platform
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)

from clawchat_gateway.config import ClawChatConfig
from clawchat_gateway.connection import ClawChatConnection, ConnectionState
from clawchat_gateway.inbound import InboundMessage, parse_inbound_message
from clawchat_gateway.protocol import (
    build_message_add_event,
    build_message_created_event,
    build_message_done_event,
    build_message_reply_event,
    new_frame_id,
)
from clawchat_gateway.stream_buffer import compute_delta

logger = logging.getLogger("clawchat_gateway.adapter")


@dataclass
class _ActiveRun:
    chat_id: str
    chat_type: str
    message_id: str
    last_text: str = ""
    reply_to_message_id: str | None = None


def check_clawchat_requirements(platform_config: Any) -> bool:
    try:
        import websockets  # noqa: F401
    except ImportError:
        logger.warning("ClawChat: websockets library not installed")
        return False
    extra = getattr(platform_config, "extra", None) or {}
    if not extra.get("websocket_url") or not extra.get("token"):
        logger.warning(
            "ClawChat: websocket_url and token are required in platforms.clawchat.extra"
        )
        return False
    return True


class ClawChatAdapter(BasePlatformAdapter):
    SUPPORTS_MESSAGE_EDITING = True
    MAX_MESSAGE_LENGTH = 0

    def __init__(self, platform_config: Any) -> None:
        super().__init__(platform_config, Platform.CLAWCHAT)
        self._clawchat_config = ClawChatConfig.from_platform_config(platform_config)
        self._connection: Any = ClawChatConnection(
            self._clawchat_config,
            on_message=self._on_message,
            on_state_change=self._on_state_change,
        )
        self._active_runs: dict[str, _ActiveRun] = {}

    async def connect(self) -> bool:
        await self._connection.start()
        return True

    async def disconnect(self) -> None:
        await self._connection.stop()

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        return {"name": chat_id, "type": "direct", "chat_id": chat_id}

    async def send_typing(self, chat_id: str, metadata: Any = None) -> None:
        return None

    async def _on_state_change(self, state: ConnectionState) -> None:
        logger.info("clawchat state -> %s", state.value)

    async def _on_message(self, frame: dict[str, Any]) -> None:
        inbound = parse_inbound_message(frame, self._clawchat_config)
        if inbound is None:
            return
        await self._handle_inbound(inbound)

    async def _handle_inbound(self, inbound: InboundMessage) -> None:
        source = self.build_source(
            chat_id=inbound.chat_id,
            sender_id=inbound.sender_id,
            chat_name=inbound.chat_id,
        )
        event = MessageEvent(
            text=inbound.text,
            message_type=MessageType.TEXT,
            source=source,
            raw_message={
                "clawchat_chat_type": inbound.chat_type,
                "clawchat_reply": inbound.reply_preview,
                "clawchat_raw": inbound.raw_message,
            },
            media_urls=inbound.media_urls,
        )
        await self.handle_message(event)

    async def send(
        self,
        chat_id: str,
        content: str = "",
        reply_to: str | None = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> SendResult:
        chat_type = self._resolve_chat_type(metadata, kwargs)
        fragments = self._build_fragments(content, metadata, kwargs)
        message_id = new_frame_id("msg")

        if self._should_use_static_mode(fragments):
            await self._connection.send_frame(
                build_message_reply_event(
                    chat_id=chat_id,
                    chat_type=chat_type,
                    fragments=fragments,
                    reply_to_message_id=reply_to,
                )
            )
            return SendResult(success=True, message_id=message_id)

        run = _ActiveRun(
            chat_id=chat_id,
            chat_type=chat_type,
            message_id=message_id,
            reply_to_message_id=reply_to,
        )
        self._active_runs[chat_id] = run

        await self._connection.send_frame(
            build_message_created_event(
                chat_id=chat_id,
                chat_type=chat_type,
                message_id=message_id,
            )
        )
        if content:
            run.last_text, delta = compute_delta(run.last_text, content)
            await self._connection.send_frame(
                build_message_add_event(
                    chat_id=chat_id,
                    chat_type=chat_type,
                    message_id=message_id,
                    full_text=run.last_text,
                    delta=delta,
                )
            )
        return SendResult(success=True, message_id=message_id)

    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        content: str,
    ) -> SendResult:
        run = self._active_runs.get(chat_id)
        if run is None:
            return SendResult(success=False, error="no active run for chat_id")

        full_text, delta = compute_delta(run.last_text, content)
        if not delta:
            return SendResult(success=True, message_id=message_id)

        await self._connection.send_frame(
            build_message_add_event(
                chat_id=chat_id,
                chat_type=run.chat_type,
                message_id=run.message_id,
                full_text=full_text,
                delta=delta,
            )
        )
        run.last_text = full_text
        return SendResult(success=True, message_id=message_id or run.message_id)

    async def on_run_complete(self, chat_id: str, final_text: str) -> None:
        run = self._active_runs.pop(chat_id, None)
        if run is None:
            return

        full_text, delta = compute_delta(run.last_text, final_text)
        if delta:
            await self._connection.send_frame(
                build_message_add_event(
                    chat_id=chat_id,
                    chat_type=run.chat_type,
                    message_id=run.message_id,
                    full_text=full_text,
                    delta=delta,
                )
            )
            run.last_text = full_text

        await self._connection.send_frame(
            build_message_done_event(
                chat_id=chat_id,
                chat_type=run.chat_type,
                message_id=run.message_id,
            )
        )
        await self._connection.send_frame(
            build_message_reply_event(
                chat_id=chat_id,
                chat_type=run.chat_type,
                fragments=self._build_fragments(run.last_text),
                reply_to_message_id=run.reply_to_message_id,
            )
        )

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: Any = None,
    ) -> SendResult:
        merged_metadata = dict(metadata or {})
        merged_metadata["media_urls"] = [image_url]
        return await self.send(
            chat_id=chat_id,
            content=caption or "",
            reply_to=reply_to,
            metadata=merged_metadata,
        )

    def _resolve_chat_type(self, metadata: Any, kwargs: dict[str, Any]) -> str:
        if isinstance(metadata, dict) and isinstance(metadata.get("chat_type"), str):
            return metadata["chat_type"]
        if isinstance(kwargs.get("chat_type"), str):
            return kwargs["chat_type"]
        return "direct"

    def _should_use_static_mode(self, fragments: list[dict[str, Any]]) -> bool:
        has_media = any(fragment.get("kind") != "text" for fragment in fragments)
        return self._clawchat_config.reply_mode != "stream" or has_media

    def _build_fragments(
        self,
        content: str = "",
        metadata: Any = None,
        kwargs: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        fragments: list[dict[str, Any]] = []
        if content:
            fragments.append({"kind": "text", "text": content})

        merged_kwargs = kwargs or {}
        media_urls: list[str] = []
        if isinstance(metadata, dict):
            raw_urls = metadata.get("media_urls") or []
            if isinstance(raw_urls, list):
                media_urls.extend(url for url in raw_urls if isinstance(url, str))
        raw_kw_urls = merged_kwargs.get("media_urls") or []
        if isinstance(raw_kw_urls, list):
            media_urls.extend(url for url in raw_kw_urls if isinstance(url, str))

        for media_url in media_urls:
            fragments.append({"kind": "image", "url": media_url})

        if not fragments:
            fragments.append({"kind": "text", "text": ""})
        return fragments
