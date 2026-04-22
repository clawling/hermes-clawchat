from clawchat_gateway.protocol import (
    build_connect_request,
    build_message_add_event,
    build_message_created_event,
    build_message_done_event,
    build_message_reply_event,
    compute_client_sign,
    extract_nonce,
    is_hello_ok,
)


def test_compute_client_sign_is_lower_hex():
    sig = compute_client_sign("openclaw", "abc123", "secret")
    assert sig == sig.lower()
    assert len(sig) == 64


def test_build_message_add_event_uses_full_text_and_delta():
    env = build_message_add_event(
        chat_id="c1",
        chat_type="direct",
        message_id="m1",
        full_text="hello",
        delta="lo",
    )
    assert env["event"] == "message.add"
    fragment = env["payload"]["message"]["fragments"][0]
    assert fragment["text"] == "hello"
    assert fragment["delta"] == "lo"


def test_build_message_reply_event_includes_reply_context_when_present():
    env = build_message_reply_event(
        chat_id="c1",
        chat_type="direct",
        fragments=[{"kind": "text", "text": "ok"}],
        reply_to_message_id="up-1",
    )
    assert env["event"] == "message.reply"
    assert env["payload"]["message"]["context"]["reply_to_message_id"] == "up-1"
