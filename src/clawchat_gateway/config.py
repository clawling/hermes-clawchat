from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ClawChatConfig:
    websocket_url: str
    base_url: str = ""
    token: str = ""
    user_id: str = ""
    reply_mode: str = "static"
    group_mode: str = "mention"
    stream_flush_interval_ms: int = 250
    stream_min_chunk_chars: int = 40
    stream_max_buffer_chars: int = 2000
    reconnect_initial_delay_ms: int = 500
    reconnect_max_delay_ms: int = 15000
    reconnect_jitter_ratio: float = 0.3
    reconnect_max_retries: float = float("inf")
    heartbeat_interval_ms: int = 20000
    heartbeat_timeout_ms: int = 10000
    ack_timeout_ms: int = 15000
    ack_auto_resend_on_timeout: bool = False
    media_local_roots: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_platform_config(cls, platform_config: Any) -> "ClawChatConfig":
        extra = getattr(platform_config, "extra", None) or {}
        stream = extra.get("stream") or {}
        return cls(
            websocket_url=extra.get("websocket_url") or extra.get("websocketUrl") or "",
            base_url=extra.get("base_url") or extra.get("baseUrl") or "",
            token=extra.get("token") or "",
            user_id=extra.get("user_id") or extra.get("userId") or "",
            reply_mode=extra.get("reply_mode") or extra.get("replyMode") or "static",
            group_mode=extra.get("group_mode") or extra.get("groupMode") or "mention",
            stream_flush_interval_ms=stream.get("flushIntervalMs", 250),
            stream_min_chunk_chars=stream.get("minChunkChars", 40),
            stream_max_buffer_chars=stream.get("maxBufferChars", 2000),
        )
