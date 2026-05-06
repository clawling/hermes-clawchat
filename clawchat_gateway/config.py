import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _read_env_file_value(name: str) -> str:
    home = os.getenv("HERMES_HOME", "").strip()
    env_path = Path(home).expanduser() / ".env" if home else Path.home() / ".hermes" / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        key, sep, value = stripped.partition("=")
        if sep and key.strip() == name:
            return value.strip().strip("\"'")
    return ""


def _read_hermes_env_value(name: str) -> str:
    try:
        from hermes_cli.config import get_env_value
    except Exception:
        return ""

    try:
        return (get_env_value(name) or "").strip()
    except Exception:
        return ""


def _get_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    for name in names:
        value = _read_hermes_env_value(name)
        if value:
            return value
    for name in names:
        value = _read_env_file_value(name).strip()
        if value:
            return value
    return ""


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
    refresh_token: str = ""
    user_id: str = ""
    reply_mode: str = "stream"
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
    media_download_dir: str = "/tmp/clawchat-media"
    show_tools_output: bool = False
    show_tool_progress: bool = False
    show_think_output: bool = False
    enable_rich_interactions: bool = False

    @classmethod
    def from_platform_config(cls, platform_config: Any) -> "ClawChatConfig":
        extra = getattr(platform_config, "extra", None) or {}
        stream = extra.get("stream") or {}
        media_roots_env = _get_env("CLAWCHAT_MEDIA_LOCAL_ROOTS")
        media_local_roots = (
            tuple(p.strip() for p in media_roots_env.split(os.pathsep) if p.strip())
            if media_roots_env
            else _get_alias(extra, "media_local_roots", "mediaLocalRoots", ())
        )
        show_tools_output = bool(
            _get_alias(extra, "show_tools_output", "showToolsOutput", False)
        )
        show_tool_progress = bool(
            _get_alias(
                extra,
                "show_tool_progress",
                "showToolProgress",
                show_tools_output,
            )
        )
        return cls(
            websocket_url=_get_env("CLAWCHAT_WEBSOCKET_URL", "CLAWCHAT_WS_URL")
            or _get_alias(extra, "websocket_url", "websocketUrl", ""),
            base_url=_get_env("CLAWCHAT_BASE_URL")
            or _get_alias(extra, "base_url", "baseUrl", ""),
            token=_get_env("CLAWCHAT_TOKEN") or extra.get("token") or "",
            refresh_token=_get_env("CLAWCHAT_REFRESH_TOKEN")
            or _get_alias(extra, "refresh_token", "refreshToken", ""),
            user_id=_get_env("CLAWCHAT_USER_ID")
            or _get_alias(extra, "user_id", "userId", ""),
            reply_mode=_get_env("CLAWCHAT_REPLY_MODE")
            or _get_alias(extra, "reply_mode", "replyMode", "stream"),
            group_mode=_get_env("CLAWCHAT_GROUP_MODE")
            or _get_alias(extra, "group_mode", "groupMode", "mention"),
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
            media_download_dir=_get_alias(
                extra, "media_download_dir", "mediaDownloadDir", "/tmp/clawchat-media"
            ),
            show_tools_output=show_tools_output,
            show_tool_progress=show_tool_progress,
            show_think_output=bool(
                _get_alias(extra, "show_think_output", "showThinkOutput", False)
            ),
            enable_rich_interactions=bool(
                _get_alias(
                    extra,
                    "enable_rich_interactions",
                    "enableRichInteractions",
                    False,
                )
            ),
        )
