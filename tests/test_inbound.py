from clawchat_gateway.config import ClawChatConfig
from clawchat_gateway.inbound import parse_inbound_message


def test_group_message_requires_mention_in_mention_mode():
    cfg = ClawChatConfig(
        websocket_url="wss://x",
        token="t",
        user_id="bot",
        group_mode="mention",
    )
    env = {
        "chat_id": "g1",
        "chat_type": "group",
        "sender": {"id": "u1", "nick_name": "alice"},
        "payload": {
            "message": {
                "fragments": [{"kind": "text", "text": "hello"}],
                "context": {"mentions": [{"id": "other"}]},
            }
        },
    }

    inbound = parse_inbound_message(env, cfg)

    assert inbound is None


def test_reply_preview_is_preserved():
    cfg = ClawChatConfig(websocket_url="wss://x", token="t", user_id="bot")
    env = {
        "chat_id": "u1",
        "chat_type": "direct",
        "sender": {"id": "u1", "nick_name": "alice"},
        "payload": {
            "message": {
                "fragments": [{"kind": "text", "text": "hello"}],
                "context": {
                    "reply": {
                        "id": "u2",
                        "nick_name": "bob",
                        "fragments": [{"kind": "text", "text": "old"}],
                    }
                },
            }
        },
    }

    inbound = parse_inbound_message(env, cfg)

    assert inbound.reply_preview["id"] == "u2"
    assert inbound.text == "hello"
