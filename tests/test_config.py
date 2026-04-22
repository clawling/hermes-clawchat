from clawchat_gateway.config import ClawChatConfig


def test_config_defaults():
    cfg = ClawChatConfig.from_platform_config(
        type(
            "PC",
            (),
            {
                "extra": {
                    "websocket_url": "wss://chat.example/ws",
                    "token": "tok",
                    "user_id": "u1",
                }
            },
        )()
    )
    assert cfg.reply_mode == "static"
    assert cfg.group_mode == "mention"
    assert cfg.stream_flush_interval_ms == 250
    assert cfg.stream_min_chunk_chars == 40
    assert cfg.stream_max_buffer_chars == 2000


def test_config_accepts_nested_openclaw_names():
    cfg = ClawChatConfig.from_platform_config(
        type(
            "PC",
            (),
            {
                "extra": {
                    "websocketUrl": "wss://chat.example/ws",
                    "baseUrl": "https://api.example",
                    "token": "tok",
                    "userId": "u1",
                    "replyMode": "stream",
                    "groupMode": "all",
                    "stream": {
                        "flushIntervalMs": 100,
                        "minChunkChars": 8,
                        "maxBufferChars": 512,
                    },
                }
            },
        )()
    )
    assert cfg.reply_mode == "stream"
    assert cfg.group_mode == "all"
    assert cfg.stream_flush_interval_ms == 100
