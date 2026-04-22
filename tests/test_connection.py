import asyncio

import pytest

from clawchat_gateway.config import ClawChatConfig
from clawchat_gateway.connection import ClawChatConnection, ConnectionState

from tests.fake_ws import FakeClawChatServer


def _cfg(**overrides) -> ClawChatConfig:
    base = dict(
        websocket_url="ws://fake",
        token="tok",
        user_id="bot",
        reconnect_initial_delay_ms=10,
        reconnect_max_delay_ms=40,
        reconnect_jitter_ratio=0.0,
        reconnect_max_retries=3,
        heartbeat_interval_ms=30_000,
        heartbeat_timeout_ms=60_000,
    )
    base.update(overrides)
    return ClawChatConfig(**base)


async def _wait_until(predicate, *, timeout: float = 1.0, sleep=asyncio.sleep):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await sleep(0.01)
    raise AssertionError("timed out waiting for condition")


async def _wait_for_connect(srv: FakeClawChatServer, *, count: int = 1):
    await _wait_until(lambda: len(srv.connect_calls) >= count)


async def _complete_handshake(srv: FakeClawChatServer) -> dict[str, object]:
    await _wait_for_connect(srv)
    srv.enqueue_from_server(
        {
            "type": "event",
            "id": "e1",
            "event": "connect.challenge",
            "payload": {"nonce": "N"},
        }
    )
    req = await srv.read_client_frame(timeout=1.0)
    srv.enqueue_from_server(
        {
            "type": "res",
            "id": "r1",
            "requestId": req["id"],
            "payload": {"type": "hello-ok"},
        }
    )
    return req


async def test_handshake_reaches_ready(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)
    seen = []

    async def on_message(_frame):
        pass

    async def on_state(state):
        seen.append(state)

    conn = ClawChatConnection(
        _cfg(),
        on_message=on_message,
        on_state_change=on_state,
    )
    await conn.start()
    try:
        req = await _complete_handshake(srv)
        assert req["method"] == "connect"
        await _wait_until(lambda: conn.is_ready)
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
        _cfg(),
        on_message=on_message,
    )
    await conn.start()
    try:
        await _wait_for_connect(srv)
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


async def test_bearer_auth_header_is_sent_on_connect(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)

    async def on_message(_frame):
        pass

    conn = ClawChatConnection(_cfg(token="tok-123"), on_message=on_message)
    await conn.start()
    try:
        await _wait_until(lambda: bool(srv.connect_calls))
        headers = srv.connect_calls[0]["kwargs"].get("additional_headers") or {}
        assert headers["Authorization"] == "Bearer tok-123"
    finally:
        await conn.stop()


async def test_wrong_request_id_times_out_without_ready(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)
    monkeypatch.setattr("clawchat_gateway.connection.HANDSHAKE_TIMEOUT_SECONDS", 0.05)
    seen_states = []

    async def on_message(_frame):
        pass

    async def on_state(state):
        seen_states.append(state)

    conn = ClawChatConnection(
        _cfg(reconnect_max_retries=0),
        on_message=on_message,
        on_state_change=on_state,
    )
    await conn.start()
    try:
        await _wait_for_connect(srv)
        srv.enqueue_from_server(
            {
                "type": "event",
                "id": "e1",
                "event": "connect.challenge",
                "payload": {"nonce": "N"},
            }
        )
        req = await srv.read_client_frame(timeout=1.0)
        srv.enqueue_from_server(
            {
                "type": "res",
                "id": "r1",
                "requestId": "wrong-id",
                "payload": {"type": "hello-ok"},
            }
        )
        await _wait_until(lambda: ConnectionState.CLOSED in seen_states, timeout=0.3)
        assert req["method"] == "connect"
        assert conn.is_ready is False
        assert ConnectionState.READY not in seen_states
    finally:
        await conn.stop()


async def test_queued_outbound_frame_flushes_after_ready(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)

    async def on_message(_frame):
        pass

    conn = ClawChatConnection(_cfg(), on_message=on_message)
    await conn.start()
    try:
        await conn.send_frame({"type": "event", "id": "m1", "event": "message.reply"})
        req = await _complete_handshake(srv)
        assert req["method"] == "connect"
        await _wait_until(lambda: conn.is_ready)
        queued = await srv.read_client_frame(timeout=1.0)
        assert queued["id"] == "m1"
        assert queued["event"] == "message.reply"
    finally:
        await conn.stop()


async def test_queued_frame_survives_failed_flush_and_reconnect(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)

    async def on_message(_frame):
        pass

    conn = ClawChatConnection(_cfg(), on_message=on_message)
    await conn.start()
    try:
        await conn.send_frame({"type": "event", "id": "queued-1", "event": "message.reply"})

        await _wait_for_connect(srv)
        srv.enqueue_from_server(
            {
                "type": "event",
                "id": "e1",
                "event": "connect.challenge",
                "payload": {"nonce": "N"},
            }
        )
        req = await srv.read_client_frame(timeout=1.0)
        real_send = conn._ws.send
        failed = False

        async def flaky_send(text: str):
            nonlocal failed
            if not failed:
                failed = True
                raise ConnectionError("flush failed")
            await real_send(text)

        monkeypatch.setattr(conn._ws, "send", flaky_send)
        srv.enqueue_from_server(
            {
                "type": "res",
                "id": "r1",
                "requestId": req["id"],
                "payload": {"type": "hello-ok"},
            }
        )

        await _wait_until(lambda: len(srv.connect_calls) >= 2, timeout=0.3)
        req2 = await _complete_handshake(srv)
        assert req2["method"] == "connect"
        await _wait_until(lambda: conn.is_ready)
        replayed = await srv.read_client_frame(timeout=1.0)
        assert replayed["id"] == "queued-1"
    finally:
        await conn.stop()


async def test_ready_send_failure_requeues_for_next_connection(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)

    async def on_message(_frame):
        pass

    conn = ClawChatConnection(_cfg(), on_message=on_message)
    await conn.start()
    try:
        await _complete_handshake(srv)
        await _wait_until(lambda: conn.is_ready)

        async def broken_send(_text: str):
            raise ConnectionError("socket going away")

        monkeypatch.setattr(conn._ws, "send", broken_send)

        with pytest.raises(ConnectionError):
            await conn.send_frame({"type": "event", "id": "direct-1", "event": "message.reply"})

        await srv.disconnect()
        await _wait_until(lambda: len(srv.connect_calls) >= 2, timeout=0.3)
        req2 = await _complete_handshake(srv)
        assert req2["method"] == "connect"
        await _wait_until(lambda: conn.is_ready)
        replayed = await srv.read_client_frame(timeout=1.0)
        assert replayed["id"] == "direct-1"
    finally:
        await conn.stop()


async def test_backoff_progresses_for_repeated_connect_failures(monkeypatch):
    srv = FakeClawChatServer()
    srv.set_auto_fail(True)
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)
    monkeypatch.setattr("clawchat_gateway.connection.random.uniform", lambda _a, _b: 0.0)

    real_sleep = asyncio.sleep
    sleep_calls = []

    async def recording_sleep(secs: float):
        sleep_calls.append(secs)
        await real_sleep(0)

    monkeypatch.setattr("clawchat_gateway.connection.asyncio.sleep", recording_sleep)

    async def on_message(_frame):
        pass

    conn = ClawChatConnection(_cfg(reconnect_max_retries=2), on_message=on_message)
    await conn.start()
    try:
        await real_sleep(0.05)
    finally:
        await conn.stop()

    assert len(srv.connect_calls) >= 3
    assert sleep_calls[:2] == [0.01, 0.02]


async def test_backoff_progresses_for_flapping_ready_connections(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)
    monkeypatch.setattr("clawchat_gateway.connection.random.uniform", lambda _a, _b: 0.0)

    real_sleep = asyncio.sleep
    sleep_calls = []
    seen_states = []

    async def recording_sleep(secs: float):
        sleep_calls.append(secs)
        await real_sleep(0)

    monkeypatch.setattr("clawchat_gateway.connection.asyncio.sleep", recording_sleep)

    async def on_message(_frame):
        pass

    async def on_state(state):
        seen_states.append(state)

    conn = ClawChatConnection(
        _cfg(reconnect_max_retries=2),
        on_message=on_message,
        on_state_change=on_state,
    )
    await conn.start()
    try:
        for ready_count in range(2):
            await _wait_until(lambda: len(srv.connect_calls) > ready_count, sleep=real_sleep)
            await _complete_handshake(srv)
            await _wait_until(
                lambda: seen_states.count(ConnectionState.READY) > ready_count,
                sleep=real_sleep,
            )
            await srv.disconnect()

        await _wait_until(lambda: len(sleep_calls) >= 2, sleep=real_sleep)
    finally:
        await conn.stop()

    assert sleep_calls[:2] == [0.01, 0.02]
