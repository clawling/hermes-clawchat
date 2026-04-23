"""Minimal stubs of hermes-agent types for unit testing the adapter.

We install these into sys.modules so that `from gateway.platforms.base import ...`
resolves to these stubs when tests run.
"""

from __future__ import annotations

import enum
import sys
import types
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional


class _Platform(enum.Enum):
    CLAWLING = "clawling"
    QQBOT = "qqbot"
    CLAWCHAT = "clawchat"


class _MessageType(enum.Enum):
    TEXT = "text"
    IMAGE = "image"


@dataclass
class _SessionSource:
    platform: Any
    chat_id: str
    user_id: str = ""
    chat_name: str = ""
    chat_type: str = "dm"
    thread_id: Optional[str] = None


@dataclass
class _MessageEvent:
    text: str
    message_type: _MessageType = _MessageType.TEXT
    source: Any = None
    raw_message: Any = None
    message_id: Optional[str] = None
    media_urls: List[str] = field(default_factory=list)
    media_types: List[str] = field(default_factory=list)
    reply_to_message_id: Optional[str] = None
    reply_to_text: Optional[str] = None
    auto_skill: Any = None
    channel_prompt: Optional[str] = None
    internal: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class _SendResult:
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    raw_response: Any = None
    retryable: bool = False


class _BasePlatformAdapter:
    def __init__(self, config: Any, platform: Any):
        self.config = config
        self.platform = platform
        self.handled: List[_MessageEvent] = []

    def build_source(
        self,
        *,
        chat_id: str,
        user_id: str = "",
        chat_name: str = "",
        chat_type: str = "dm",
        **kw,
    ):
        return _SessionSource(
            platform=self.platform,
            chat_id=chat_id,
            user_id=user_id,
            chat_name=chat_name or chat_id,
            chat_type=chat_type,
        )

    async def handle_message(self, event: _MessageEvent) -> None:
        self.handled.append(event)


def install() -> None:
    """Inject stub modules so `from gateway.platforms.base import ...` works."""
    base = types.ModuleType("gateway.platforms.base")
    base.BasePlatformAdapter = _BasePlatformAdapter
    base.MessageEvent = _MessageEvent
    base.MessageType = _MessageType
    base.SendResult = _SendResult
    base.SessionSource = _SessionSource

    platforms = types.ModuleType("gateway.platforms")
    gateway = types.ModuleType("gateway")
    gateway_config = types.ModuleType("gateway.config")
    gateway_config.Platform = _Platform

    sys.modules.setdefault("gateway", gateway)
    sys.modules.setdefault("gateway.platforms", platforms)
    sys.modules["gateway.platforms.base"] = base
    sys.modules["gateway.config"] = gateway_config
