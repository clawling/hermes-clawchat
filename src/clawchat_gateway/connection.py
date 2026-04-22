"""ClawChat WebSocket connection lifecycle."""

from __future__ import annotations

import asyncio
import enum
import logging
import random
from collections import deque
from typing import Any, Awaitable, Callable

try:
    from websockets.asyncio.client import connect as _ws_connect_impl
except ImportError:  # pragma: no cover
    _ws_connect_impl = None  # type: ignore[assignment]

from clawchat_gateway.config import ClawChatConfig
from clawchat_gateway.protocol import (
    build_connect_request,
    compute_client_sign,
    decode_frame,
    encode_frame,
    extract_nonce,
    is_hello_ok,
    new_frame_id,
)

logger = logging.getLogger("clawchat_gateway.connection")

HANDSHAKE_TIMEOUT_SECONDS = 10.0
SEND_QUEUE_MAX = 128
CLIENT_ID = "hermes-agent"
CLIENT_VERSION = "hermes-clawchat/0.1"
BACKOFF_RESET_AFTER_SECONDS = 5.0


async def _ws_connect(url: str, **kwargs: Any) -> Any:
    if _ws_connect_impl is None:
        raise RuntimeError("websockets library not available")
    return await _ws_connect_impl(url, **kwargs)


class ConnectionState(str, enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    HANDSHAKING = "handshaking"
    READY = "ready"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


OnMessage = Callable[[dict[str, Any]], Awaitable[None]]
OnStateChange = Callable[[ConnectionState], Awaitable[None]]


class ClawChatConnection:
    def __init__(
        self,
        config: ClawChatConfig,
        *,
        on_message: OnMessage,
        on_state_change: OnStateChange | None = None,
    ) -> None:
        self._cfg = config
        self._on_message = on_message
        self._on_state_change = on_state_change
        self._state = ConnectionState.DISCONNECTED
        self._ws: Any = None
        self._stopping = False
        self._supervisor_task: asyncio.Task[None] | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._hello_wait: asyncio.Future[bool] | None = None
        self._pending_connect_id: str | None = None
        self._send_queue: deque[str] = deque()
        self._flushing_send_queue = False

    async def start(self) -> None:
        if self._supervisor_task is not None:
            return
        self._stopping = False
        self._supervisor_task = asyncio.create_task(
            self._supervisor(),
            name="clawchat-supervisor",
        )

    async def stop(self) -> None:
        self._stopping = True
        await self._set_state(ConnectionState.CLOSED)
        if self._read_task is not None:
            self._read_task.cancel()
        if self._hello_wait is not None and not self._hello_wait.done():
            self._hello_wait.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
        if self._supervisor_task is not None:
            self._supervisor_task.cancel()
            try:
                await self._supervisor_task
            except (asyncio.CancelledError, Exception):
                pass
            self._supervisor_task = None

    async def send_frame(self, frame: dict[str, Any]) -> None:
        text = encode_frame(frame)
        if (
            self._state == ConnectionState.READY
            and self._ws is not None
            and not self._send_queue
            and not self._flushing_send_queue
        ):
            try:
                await self._ws.send(text)
            except Exception:
                self._enqueue_text(text, front=True)
                raise
            return
        self._enqueue_text(text)

    @property
    def is_ready(self) -> bool:
        return self._state == ConnectionState.READY

    async def _set_state(self, state: ConnectionState) -> None:
        if self._state == state:
            return
        self._state = state
        if self._on_state_change is None:
            return
        try:
            await self._on_state_change(state)
        except Exception:  # noqa: BLE001
            logger.exception("on_state_change raised")

    async def _supervisor(self) -> None:
        delay_seconds = self._cfg.reconnect_initial_delay_ms / 1000.0
        max_delay_seconds = self._cfg.reconnect_max_delay_ms / 1000.0
        max_retries = self._cfg.reconnect_max_retries
        retries = 0
        while not self._stopping:
            try:
                await self._set_state(ConnectionState.CONNECTING)
                stable_session = await self._run_one_connection()
                if stable_session:
                    delay_seconds = self._cfg.reconnect_initial_delay_ms / 1000.0
                    retries = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("clawchat connection lost: %s", exc)
            if self._stopping:
                break
            retries += 1
            if retries > max_retries:
                break
            await self._set_state(ConnectionState.RECONNECTING)
            jitter = random.uniform(0.0, delay_seconds * self._cfg.reconnect_jitter_ratio)
            await asyncio.sleep(delay_seconds + jitter)
            delay_seconds = min(delay_seconds * 2.0, max_delay_seconds)
        await self._set_state(ConnectionState.CLOSED)

    async def _run_one_connection(self) -> bool:
        ws = await _ws_connect(
            self._cfg.websocket_url,
            additional_headers={"Authorization": f"Bearer {self._cfg.token}"},
            ping_interval=self._cfg.heartbeat_interval_ms / 1000.0,
            ping_timeout=self._cfg.heartbeat_timeout_ms / 1000.0,
        )
        self._ws = ws
        self._pending_connect_id = None
        ready_started_at: float | None = None
        await self._set_state(ConnectionState.HANDSHAKING)

        loop = asyncio.get_running_loop()
        self._hello_wait = loop.create_future()
        self._read_task = asyncio.create_task(self._read_loop(ws), name="clawchat-read")
        try:
            await asyncio.wait_for(self._hello_wait, timeout=HANDSHAKE_TIMEOUT_SECONDS)
            await self._set_state(ConnectionState.READY)
            ready_started_at = loop.time()
            await self._flush_send_queue(ws)
            await self._read_task
        finally:
            if self._read_task is not None and not self._read_task.done():
                self._read_task.cancel()
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None
        if ready_started_at is None:
            return False
        return (loop.time() - ready_started_at) >= BACKOFF_RESET_AFTER_SECONDS

    async def _flush_send_queue(self, ws: Any) -> None:
        self._flushing_send_queue = True
        try:
            while self._send_queue:
                text = self._send_queue[0]
                await ws.send(text)
                self._send_queue.popleft()
        finally:
            self._flushing_send_queue = False

    async def _read_loop(self, ws: Any) -> None:
        async for raw in ws:
            try:
                frame = decode_frame(raw)
            except (TypeError, ValueError) as exc:
                logger.warning("clawchat dropped malformed frame: %s", exc)
                continue
            await self._dispatch_inbound(frame)

    async def _dispatch_inbound(self, frame: dict[str, Any]) -> None:
        ftype = frame.get("type")
        if ftype == "event" and frame.get("event") == "connect.challenge":
            await self._handle_challenge(frame)
            return
        if ftype == "res" and self._hello_wait is not None and not self._hello_wait.done():
            await self._maybe_finish_handshake(frame)
            return
        if (
            self._state == ConnectionState.READY
            and ftype == "event"
            and frame.get("event") == "message.send"
        ):
            await self._on_message(frame)
            return

    async def _handle_challenge(self, frame: dict[str, Any]) -> None:
        nonce = extract_nonce(frame)
        if not nonce:
            logger.warning("challenge missing nonce")
            return
        req_id = new_frame_id("req")
        self._pending_connect_id = req_id
        sign = compute_client_sign(CLIENT_ID, nonce, self._cfg.token)
        connect_req = build_connect_request(
            frame_id=req_id,
            token=self._cfg.token,
            client_id=CLIENT_ID,
            client_version=CLIENT_VERSION,
            sign=sign,
        )
        await self._ws.send(encode_frame(connect_req))

    async def _maybe_finish_handshake(self, frame: dict[str, Any]) -> None:
        if self._pending_connect_id and is_hello_ok(frame, self._pending_connect_id):
            if self._hello_wait is not None and not self._hello_wait.done():
                self._hello_wait.set_result(True)

    def _enqueue_text(self, text: str, *, front: bool = False) -> None:
        if len(self._send_queue) >= SEND_QUEUE_MAX:
            logger.warning("clawchat send queue full, dropping oldest frame")
            if front:
                self._send_queue.pop()
            else:
                self._send_queue.popleft()
        if front:
            self._send_queue.appendleft(text)
        else:
            self._send_queue.append(text)
