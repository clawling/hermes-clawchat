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


def test_extract_nonce_returns_none_when_payload_is_not_dict():
    assert extract_nonce({"payload": "bad"}) is None


def test_extract_nonce_returns_none_when_payload_data_is_not_dict():
    assert extract_nonce({"payload": {"data": "bad"}}) is None


def test_extract_nonce_reads_nonce_from_nested_data():
    assert extract_nonce({"payload": {"data": {"nonce": "abc123"}}}) == "abc123"


def test_is_hello_ok_returns_false_when_payload_is_not_dict():
    assert (
        is_hello_ok(
            {"type": "res", "requestId": "req-1", "payload": "bad"},
            "req-1",
        )
        is False
    )


def test_is_hello_ok_returns_false_for_wrong_payload_type():
    assert (
        is_hello_ok(
            {"type": "res", "requestId": "req-1", "payload": {"type": "hello-no"}},
            "req-1",
        )
        is False
    )
