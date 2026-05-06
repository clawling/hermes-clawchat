from uuid import UUID

from clawchat_gateway.protocol import (
    build_connect_request,
    build_message_add_event,
    build_message_created_event,
    build_message_done_event,
    build_message_failed_event,
    build_message_reply_event,
    build_typing_update_event,
    compute_client_sign,
    extract_nonce,
    is_hello_ok,
    new_frame_id,
)


def _assert_prefixed_uuid(value: str, prefix: str) -> None:
    assert value.startswith(f"{prefix}-")
    UUID(value.removeprefix(f"{prefix}-"))


def test_compute_client_sign_is_lower_hex():
    sig = compute_client_sign("openclaw", "abc123", "secret")
    assert sig == sig.lower()
    assert len(sig) == 64


def test_new_frame_id_uses_prefixed_uuid():
    _assert_prefixed_uuid(new_frame_id("trace"), "trace")


def test_build_connect_request_uses_realtime_connect_event():
    env = build_connect_request(
        frame_id="trace-1",
        token="tok",
        client_id="client-1",
        client_version="v1",
        sign="sig",
        device_id="dev-1",
        capabilities={"streaming": True},
    )

    assert env["version"] == "2"
    assert env["event"] == "connect"
    assert env["trace_id"] == "trace-1"
    assert env["payload"] == {
        "token": "tok",
        "client_id": "client-1",
        "client_version": "v1",
        "device_id": "dev-1",
        "capabilities": {"streaming": True},
        "sign": "sig",
    }


def test_client_originated_business_frames_omit_root_chat_type_and_sender():
    frames = [
        build_message_created_event(chat_id="c1", chat_type="direct", message_id="m1"),
        build_message_add_event(chat_id="c1", chat_type="direct", message_id="m1", full_text="hi", delta="hi", sequence=0),
        build_message_done_event(chat_id="c1", chat_type="direct", message_id="m1", fragments=[{"kind": "text", "text": "hi"}], sequence=0),
        build_message_failed_event(chat_id="c1", chat_type="direct", message_id="m1", sequence=0, reason="boom"),
        build_message_reply_event(chat_id="c1", chat_type="direct", message_id="m1", fragments=[{"kind": "text", "text": "hi"}], include_message_id=True),
        build_typing_update_event(chat_id="c1", chat_type="direct", active=True),
    ]
    for frame in frames:
        assert frame["chat_id"] == "c1"
        assert "chat_type" not in frame
        assert "sender" not in frame


def test_build_message_add_event_uses_full_text_and_delta():
    env = build_message_add_event(
        chat_id="c1",
        chat_type="direct",
        message_id="m1",
        full_text="hello",
        delta="lo",
        sequence=3,
    )
    assert env["version"] == "2"
    assert env["event"] == "message.add"
    _assert_prefixed_uuid(env["trace_id"], "trace")
    assert env["payload"]["message_id"] == "m1"
    assert env["payload"]["sequence"] == 3
    assert env["payload"]["mutation"] == {"type": "append", "target_fragment_index": None}
    assert env["payload"]["streaming"]["status"] == "streaming"
    assert env["payload"]["streaming"]["sequence"] == 3
    fragment = env["payload"]["fragments"][0]
    assert fragment["text"] == "hello"
    assert fragment["delta"] == "lo"


def test_build_message_done_event_uses_v2_stream_payload():
    env = build_message_done_event(
        chat_id="c1",
        chat_type="direct",
        message_id="m1",
        fragments=[{"kind": "text", "text": "hello"}],
        sequence=3,
    )

    assert env["version"] == "2"
    assert env["event"] == "message.done"
    assert env["payload"]["message_id"] == "m1"
    assert env["payload"]["fragments"] == [{"kind": "text", "text": "hello"}]
    assert env["payload"]["streaming"]["status"] == "done"
    assert env["payload"]["streaming"]["sequence"] == 3
    assert isinstance(env["payload"]["completed_at"], int)


def test_build_message_reply_event_includes_reply_context_when_present():
    env = build_message_reply_event(
        chat_id="c1",
        chat_type="direct",
        message_id="m1",
        fragments=[{"kind": "text", "text": "ok"}],
        reply_to_message_id="up-1",
    )
    assert env["version"] == "2"
    assert env["event"] == "message.reply"
    assert "message_id" not in env["payload"]
    assert env["payload"]["message_mode"] == "normal"
    assert env["payload"]["message"]["body"]["fragments"] == [{"kind": "text", "text": "ok"}]
    assert env["payload"]["message"]["context"]["mentions"] == []
    assert env["payload"]["message"]["context"]["reply"]["reply_to_msg_id"] == "up-1"
    assert env["payload"]["message"]["context"]["reply"]["reply_preview"] is None


def test_build_message_reply_event_can_include_stream_message_id_for_finalize():
    env = build_message_reply_event(
        chat_id="c1",
        chat_type="direct",
        message_id="m1",
        fragments=[{"kind": "text", "text": "ok"}],
        include_message_id=True,
    )
    assert env["payload"]["message_id"] == "m1"


def test_build_message_failed_event_uses_failed_stream_payload():
    env = build_message_failed_event(
        chat_id="c1",
        chat_type="direct",
        message_id="m1",
        sequence=2,
        reason="boom",
    )
    assert env["event"] == "message.failed"
    assert env["payload"]["message_id"] == "m1"
    assert env["payload"]["sequence"] == 2
    assert env["payload"]["streaming"]["status"] == "failed"
    assert env["payload"]["streaming"]["sequence"] == 2
    assert env["payload"]["fragments"] == [{"kind": "text", "text": "boom"}]
    assert env["payload"]["completed_at"] == env["payload"]["streaming"]["completed_at"]


def test_build_typing_update_event():
    env = build_typing_update_event(chat_id="c1", chat_type="direct", active=True)

    assert env["version"] == "2"
    assert env["event"] == "typing.update"
    _assert_prefixed_uuid(env["trace_id"], "trace")
    assert env["chat_id"] == "c1"
    assert "chat_type" not in env
    assert env["payload"]["is_typing"] is True


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


def test_is_hello_ok_accepts_realtime_hello_event():
    assert is_hello_ok({"version": "2", "event": "hello-ok", "payload": {}}, "req-1") is True
