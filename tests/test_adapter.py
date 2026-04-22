from __future__ import annotations

from types import SimpleNamespace

from clawchat_gateway.adapter import ClawChatAdapter
from clawchat_gateway.inbound import InboundMessage
from clawchat_gateway.stream_buffer import compute_delta


class FakeConnection:
    def __init__(self) -> None:
        self.sent_frames: list[dict] = []
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send_frame(self, frame: dict) -> None:
        self.sent_frames.append(frame)


def _make_adapter(**extra) -> ClawChatAdapter:
    adapter = ClawChatAdapter(
        SimpleNamespace(
            extra={
                "websocket_url": "ws://x",
                "token": "t",
                "user_id": "bot",
                **extra,
            }
        )
    )
    adapter._connection = FakeConnection()
    return adapter


def test_compute_delta_uses_suffix_when_content_extends():
    full, delta = compute_delta("abc", "abcdef")
    assert full == "abcdef"
    assert delta == "def"


def test_compute_delta_falls_back_to_full_on_prefix_reset():
    full, delta = compute_delta("abcdef", "xyz")
    assert full == "xyz"
    assert delta == "xyz"


async def test_on_message_builds_message_event():
    adapter = _make_adapter()
    inbound = InboundMessage(
        chat_id="u1",
        chat_type="direct",
        sender_id="u1",
        sender_name="alice",
        text="hello",
        raw_message={"x": 1},
    )

    await adapter._handle_inbound(inbound)

    assert len(adapter.handled) == 1
    assert adapter.handled[0].text == "hello"
    assert adapter.handled[0].raw_message == {
        "clawchat_chat_type": "direct",
        "clawchat_reply": None,
        "clawchat_raw": {"x": 1},
    }


async def test_send_emits_message_reply_for_static_mode():
    adapter = _make_adapter()

    result = await adapter.send(chat_id="u1", content="hi")

    assert result.success is True
    assert adapter._connection.sent_frames[0]["event"] == "message.reply"
    assert adapter._connection.sent_frames[0]["payload"]["message"]["fragments"] == [
        {"kind": "text", "text": "hi"}
    ]


async def test_send_emits_message_created_then_add_for_stream_mode():
    adapter = _make_adapter(reply_mode="stream")

    result = await adapter.send(chat_id="u1", content="hello")

    assert result.success is True
    assert [frame["event"] for frame in adapter._connection.sent_frames] == [
        "message.created",
        "message.add",
    ]
    message_id = result.message_id
    assert adapter._connection.sent_frames[0]["payload"]["message"]["id"] == message_id
    assert (
        adapter._connection.sent_frames[1]["payload"]["message"]["fragments"][0]["delta"]
        == "hello"
    )


async def test_edit_message_emits_message_add_for_stream_mode():
    adapter = _make_adapter(reply_mode="stream")
    first = await adapter.send(chat_id="u1", content="hello")
    adapter._connection.sent_frames.clear()

    result = await adapter.edit_message(
        chat_id="u1",
        message_id=first.message_id or "",
        content="hello world",
    )

    assert result.success is True
    assert [frame["event"] for frame in adapter._connection.sent_frames] == ["message.add"]
    fragment = adapter._connection.sent_frames[0]["payload"]["message"]["fragments"][0]
    assert fragment["text"] == "hello world"
    assert fragment["delta"] == " world"


async def test_on_run_complete_emits_message_done_then_reply():
    adapter = _make_adapter(reply_mode="stream")
    first = await adapter.send(chat_id="u1", content="hello")
    adapter._connection.sent_frames.clear()

    await adapter.on_run_complete(chat_id="u1", final_text="hello world")

    assert [frame["event"] for frame in adapter._connection.sent_frames] == [
        "message.add",
        "message.done",
        "message.reply",
    ]
    assert adapter._connection.sent_frames[1]["payload"]["message"]["id"] == first.message_id
    assert adapter._connection.sent_frames[2]["payload"]["message"]["fragments"] == [
        {"kind": "text", "text": "hello world"}
    ]
    assert "u1" not in adapter._active_runs


async def test_send_forces_static_mode_when_outbound_media_exists():
    adapter = _make_adapter(reply_mode="stream")

    result = await adapter.send(
        chat_id="u1",
        content="look",
        metadata={"media_urls": ["https://example.com/a.png"]},
    )

    assert result.success is True
    assert [frame["event"] for frame in adapter._connection.sent_frames] == ["message.reply"]
    assert adapter._connection.sent_frames[0]["payload"]["message"]["fragments"] == [
        {"kind": "text", "text": "look"},
        {"kind": "image", "url": "https://example.com/a.png"},
    ]
