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


async def test_on_message_maps_reply_preview_to_message_event_fields():
    adapter = _make_adapter()
    inbound = InboundMessage(
        chat_id="u1",
        chat_type="direct",
        sender_id="u1",
        sender_name="alice",
        text="hello",
        raw_message={"x": 1},
        reply_preview={
            "id": "msg-42",
            "fragments": [
                {"kind": "text", "text": "older"},
                {"kind": "image", "url": "https://example.com/p.png"},
                {"kind": "text", "text": " message"},
            ],
        },
    )

    await adapter._handle_inbound(inbound)

    event = adapter.handled[0]
    assert event.reply_to_message_id == "msg-42"
    assert event.reply_to_text == "older message"


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


async def test_edit_message_targets_run_by_message_id_with_overlapping_streams():
    adapter = _make_adapter(reply_mode="stream")
    first = await adapter.send(chat_id="u1", content="first")
    second = await adapter.send(chat_id="u1", content="second")
    adapter._connection.sent_frames.clear()

    result = await adapter.edit_message(
        chat_id="u1",
        message_id=first.message_id or "",
        content="first expanded",
    )

    assert result.success is True
    assert [frame["event"] for frame in adapter._connection.sent_frames] == ["message.add"]
    add_frame = adapter._connection.sent_frames[0]
    assert add_frame["payload"]["message"]["id"] == first.message_id
    assert add_frame["payload"]["message"]["fragments"][0]["delta"] == " expanded"
    assert adapter._active_chat_runs["u1"] == second.message_id
    assert adapter._active_runs_by_id[first.message_id].last_text == "first expanded"
    assert adapter._active_runs_by_id[second.message_id].last_text == "second"


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
    assert first.message_id not in adapter._active_runs_by_id


async def test_on_run_complete_finalizes_requested_run_during_overlap():
    adapter = _make_adapter(reply_mode="stream")
    first = await adapter.send(chat_id="u1", content="first")
    second = await adapter.send(chat_id="u1", content="second")
    adapter._connection.sent_frames.clear()

    await adapter.on_run_complete(
        chat_id="u1",
        final_text="first final",
        message_id=first.message_id,
    )

    assert [frame["event"] for frame in adapter._connection.sent_frames] == [
        "message.add",
        "message.done",
        "message.reply",
    ]
    assert adapter._connection.sent_frames[1]["payload"]["message"]["id"] == first.message_id
    assert first.message_id not in adapter._active_runs_by_id
    assert adapter._active_chat_runs["u1"] == second.message_id


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


async def test_send_classifies_non_image_media_in_static_fallback():
    adapter = _make_adapter(reply_mode="stream")

    result = await adapter.send(
        chat_id="u1",
        content="files",
        metadata={
            "media_urls": [
                "https://example.com/report.pdf",
                "https://example.com/voice.mp3",
                "https://example.com/clip.unknown",
            ],
            "media_content_types": {
                "https://example.com/clip.unknown": "video/mp4",
            },
        },
    )

    assert result.success is True
    assert [frame["event"] for frame in adapter._connection.sent_frames] == ["message.reply"]
    assert adapter._connection.sent_frames[0]["payload"]["message"]["fragments"] == [
        {"kind": "text", "text": "files"},
        {"kind": "file", "url": "https://example.com/report.pdf"},
        {"kind": "audio", "url": "https://example.com/voice.mp3"},
        {"kind": "video", "url": "https://example.com/clip.unknown"},
    ]
