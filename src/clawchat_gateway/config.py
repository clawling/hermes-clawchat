from dataclasses import dataclass, field
from typing import Any


def _get_alias(data: dict[str, Any], snake: str, camel: str, default: Any = None) -> Any:
    if snake in data:
        return data[snake]
    if camel in data:
        return data[camel]
    return default


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
        media_local_roots = _get_alias(extra, "media_local_roots", "mediaLocalRoots", ())
        return cls(
            websocket_url=_get_alias(extra, "websocket_url", "websocketUrl", ""),
            base_url=_get_alias(extra, "base_url", "baseUrl", ""),
            token=extra.get("token") or "",
            user_id=_get_alias(extra, "user_id", "userId", ""),
            reply_mode=_get_alias(extra, "reply_mode", "replyMode", "static"),
            group_mode=_get_alias(extra, "group_mode", "groupMode", "mention"),
            stream_flush_interval_ms=_get_alias(
                stream, "flush_interval_ms", "flushIntervalMs", 250
            ),
            stream_min_chunk_chars=_get_alias(
                stream, "min_chunk_chars", "minChunkChars", 40
            ),
            stream_max_buffer_chars=_get_alias(
                stream, "max_buffer_chars", "maxBufferChars", 2000
            ),
            reconnect_initial_delay_ms=_get_alias(
                extra, "reconnect_initial_delay_ms", "reconnectInitialDelayMs", 500
            ),
            reconnect_max_delay_ms=_get_alias(
                extra, "reconnect_max_delay_ms", "reconnectMaxDelayMs", 15000
            ),
            reconnect_jitter_ratio=_get_alias(
                extra, "reconnect_jitter_ratio", "reconnectJitterRatio", 0.3
            ),
            reconnect_max_retries=_get_alias(
                extra, "reconnect_max_retries", "reconnectMaxRetries", float("inf")
            ),
            heartbeat_interval_ms=_get_alias(
                extra, "heartbeat_interval_ms", "heartbeatIntervalMs", 20000
            ),
            heartbeat_timeout_ms=_get_alias(
                extra, "heartbeat_timeout_ms", "heartbeatTimeoutMs", 10000
            ),
            ack_timeout_ms=_get_alias(extra, "ack_timeout_ms", "ackTimeoutMs", 15000),
            ack_auto_resend_on_timeout=_get_alias(
                extra, "ack_auto_resend_on_timeout", "ackAutoResendOnTimeout", False
            ),
            media_local_roots=tuple(media_local_roots),
        )
