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
    assert cfg.websocket_url == "wss://chat.example/ws"
    assert cfg.base_url == ""
    assert cfg.token == "tok"
    assert cfg.user_id == "u1"
    assert cfg.reply_mode == "stream"
    assert cfg.group_mode == "mention"
    assert cfg.stream_flush_interval_ms == 250
    assert cfg.stream_min_chunk_chars == 40
    assert cfg.stream_max_buffer_chars == 2000
    assert cfg.reconnect_initial_delay_ms == 500
    assert cfg.reconnect_max_delay_ms == 15000
    assert cfg.reconnect_jitter_ratio == 0.3
    assert cfg.reconnect_max_retries == float("inf")
    assert cfg.heartbeat_interval_ms == 20000
    assert cfg.heartbeat_timeout_ms == 10000
    assert cfg.ack_timeout_ms == 15000
    assert cfg.ack_auto_resend_on_timeout is False
    assert cfg.media_local_roots == ()
    assert cfg.show_tools_output is False
    assert cfg.show_think_output is False


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
                    "reconnectInitialDelayMs": 111,
                    "reconnect_max_delay_ms": 222,
                    "reconnectJitterRatio": 0.12,
                    "reconnect_max_retries": 7,
                    "heartbeatIntervalMs": 333,
                    "heartbeat_timeout_ms": 444,
                    "ackTimeoutMs": 555,
                    "ack_auto_resend_on_timeout": True,
                    "mediaLocalRoots": ["/tmp/a", "/tmp/b"],
                    "showToolsOutput": True,
                    "show_think_output": True,
                    "stream": {
                        "flushIntervalMs": 100,
                        "min_chunk_chars": 8,
                        "minChunkChars": 8,
                        "max_buffer_chars": 512,
                        "maxBufferChars": 512,
                    },
                }
            },
        )()
    )
    assert cfg.websocket_url == "wss://chat.example/ws"
    assert cfg.base_url == "https://api.example"
    assert cfg.token == "tok"
    assert cfg.user_id == "u1"
    assert cfg.reply_mode == "stream"
    assert cfg.group_mode == "all"
    assert cfg.reconnect_initial_delay_ms == 111
    assert cfg.reconnect_max_delay_ms == 222
    assert cfg.reconnect_jitter_ratio == 0.12
    assert cfg.reconnect_max_retries == 7
    assert cfg.heartbeat_interval_ms == 333
    assert cfg.heartbeat_timeout_ms == 444
    assert cfg.ack_timeout_ms == 555
    assert cfg.ack_auto_resend_on_timeout is True
    assert cfg.media_local_roots == ("/tmp/a", "/tmp/b")
    assert cfg.show_tools_output is True
    assert cfg.show_think_output is True
    assert cfg.stream_flush_interval_ms == 100
    assert cfg.stream_min_chunk_chars == 8
    assert cfg.stream_max_buffer_chars == 512
