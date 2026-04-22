import asyncio

from clawchat_gateway.config import ClawChatConfig
from clawchat_gateway.connection import ClawChatConnection

from tests.fake_ws import FakeClawChatServer


async def test_handshake_reaches_ready(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)
    seen = []

    async def on_message(_frame):
        pass

    async def on_state(state):
        seen.append(state)

    conn = ClawChatConnection(
        ClawChatConfig(websocket_url="ws://fake", token="tok", user_id="bot"),
        on_message=on_message,
        on_state_change=on_state,
    )
    await conn.start()
    try:
        srv.enqueue_from_server(
            {
                "type": "event",
                "id": "e1",
                "event": "connect.challenge",
                "payload": {"nonce": "N"},
            }
        )
        req = await srv.read_client_frame(timeout=1.0)
        assert req["method"] == "connect"
        srv.enqueue_from_server(
            {
                "type": "res",
                "id": "r1",
                "requestId": req["id"],
                "payload": {"type": "hello-ok"},
            }
        )
        for _ in range(20):
            if conn.is_ready:
                break
            await asyncio.sleep(0.01)
        assert conn.is_ready is True
        assert "ready" in [s.value for s in seen]
    finally:
        await conn.stop()


async def test_message_send_before_ready_is_ignored(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)
    seen_messages = []

    async def on_message(frame):
        seen_messages.append(frame)

    conn = ClawChatConnection(
        ClawChatConfig(websocket_url="ws://fake", token="tok", user_id="bot"),
        on_message=on_message,
    )
    await conn.start()
    try:
        srv.enqueue_from_server(
            {
                "type": "event",
                "id": "e1",
                "event": "connect.challenge",
                "payload": {"nonce": "N"},
            }
        )
        req = await srv.read_client_frame(timeout=1.0)
        assert req["method"] == "connect"

        srv.enqueue_from_server(
            {
                "type": "event",
                "id": "m1",
                "event": "message.send",
                "payload": {"message": {"fragments": [{"kind": "text", "text": "hi"}]}},
            }
        )
        await asyncio.sleep(0.05)

        assert seen_messages == []
        assert conn.is_ready is False
    finally:
        await conn.stop()
