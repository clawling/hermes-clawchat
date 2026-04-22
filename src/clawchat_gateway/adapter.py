"""ClawChatAdapter — BasePlatformAdapter for the ClawChat WebSocket protocol."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

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
from clawchat_gateway.media_runtime import infer_media_kind_from_mime
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
    started_order: int
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
        self._active_runs_by_id: dict[str, _ActiveRun] = {}
        self._active_chat_runs: dict[str, str] = {}
        self._run_counter = 0

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
        reply_to_message_id, reply_to_text = self._extract_reply_fields(
            inbound.reply_preview
        )
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
            reply_to_message_id=reply_to_message_id,
            reply_to_text=reply_to_text,
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
            started_order=self._next_run_order(),
            reply_to_message_id=reply_to,
        )
        self._active_runs_by_id[message_id] = run
        self._active_chat_runs[chat_id] = message_id

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
        run = self._resolve_active_run(chat_id=chat_id, message_id=message_id)
        if run is None:
            return SendResult(success=False, error="no active run for message_id")

        full_text, delta = compute_delta(run.last_text, content)
        if not delta:
            return SendResult(success=True, message_id=run.message_id)

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
        return SendResult(success=True, message_id=run.message_id)

    async def on_run_complete(
        self,
        chat_id: str,
        final_text: str,
        message_id: str | None = None,
    ) -> None:
        run = self._resolve_active_run(chat_id=chat_id, message_id=message_id)
        if run is None:
            return
        self._discard_run(run)

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

    def _next_run_order(self) -> int:
        self._run_counter += 1
        return self._run_counter

    def _resolve_active_run(
        self,
        *,
        chat_id: str,
        message_id: str | None = None,
    ) -> _ActiveRun | None:
        if message_id:
            run = self._active_runs_by_id.get(message_id)
            if run is None or run.chat_id != chat_id:
                return None
            return run
        latest_message_id = self._active_chat_runs.get(chat_id)
        if latest_message_id is None:
            return None
        return self._active_runs_by_id.get(latest_message_id)

    def _discard_run(self, run: _ActiveRun) -> None:
        self._active_runs_by_id.pop(run.message_id, None)
        latest_message_id = self._active_chat_runs.get(run.chat_id)
        if latest_message_id != run.message_id:
            return
        replacement = self._find_latest_run_for_chat(run.chat_id)
        if replacement is None:
            self._active_chat_runs.pop(run.chat_id, None)
            return
        self._active_chat_runs[run.chat_id] = replacement.message_id

    def _find_latest_run_for_chat(self, chat_id: str) -> _ActiveRun | None:
        candidates = [
            run for run in self._active_runs_by_id.values() if run.chat_id == chat_id
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda run: run.started_order)

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

        for index, media_url in enumerate(media_urls):
            fragments.append(
                {
                    "kind": self._infer_media_kind(
                        media_url=media_url,
                        index=index,
                        metadata=metadata,
                        kwargs=merged_kwargs,
                    ),
                    "url": media_url,
                }
            )

        if not fragments:
            fragments.append({"kind": "text", "text": ""})
        return fragments

    def _infer_media_kind(
        self,
        *,
        media_url: str,
        index: int,
        metadata: Any,
        kwargs: dict[str, Any],
    ) -> str:
        mime_hint = self._extract_media_mime_hint(
            media_url=media_url,
            index=index,
            metadata=metadata,
            kwargs=kwargs,
        )
        if mime_hint:
            return infer_media_kind_from_mime(mime_hint)

        path = urlparse(media_url).path.lower()
        if path.endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".heic")
        ):
            return "image"
        if path.endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")):
            return "audio"
        if path.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v")):
            return "video"
        return "file"

    def _extract_media_mime_hint(
        self,
        *,
        media_url: str,
        index: int,
        metadata: Any,
        kwargs: dict[str, Any],
    ) -> str | None:
        for carrier in (metadata, kwargs):
            hint = self._lookup_media_mime_hint(carrier, media_url, index)
            if hint:
                return hint
        return None

    def _lookup_media_mime_hint(
        self,
        carrier: Any,
        media_url: str,
        index: int,
    ) -> str | None:
        if not isinstance(carrier, dict):
            return None
        for key in ("media_content_types", "media_mime_types"):
            raw = carrier.get(key)
            if isinstance(raw, Mapping):
                hint = raw.get(media_url)
                if isinstance(hint, str):
                    return hint
            if isinstance(raw, list) and index < len(raw) and isinstance(raw[index], str):
                return raw[index]
        return None

    def _extract_reply_fields(
        self,
        reply_preview: dict[str, Any] | None,
    ) -> tuple[str | None, str | None]:
        if not isinstance(reply_preview, dict):
            return None, None

        nested_preview = reply_preview.get("reply_preview")
        preview = nested_preview if isinstance(nested_preview, dict) else reply_preview

        reply_to_message_id = None
        for key in ("id", "reply_to_msg_id"):
            value = preview.get(key)
            if isinstance(value, str) and value:
                reply_to_message_id = value
                break
            value = reply_preview.get(key)
            if isinstance(value, str) and value:
                reply_to_message_id = value
                break

        fragments = preview.get("fragments")
        text_parts: list[str] = []
        if isinstance(fragments, list):
            for fragment in fragments:
                if not isinstance(fragment, dict):
                    continue
                if fragment.get("kind") == "text" and isinstance(fragment.get("text"), str):
                    text_parts.append(fragment["text"])

        reply_to_text = "".join(text_parts) or None
        return reply_to_message_id, reply_to_text
