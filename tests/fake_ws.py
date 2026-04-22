"""In-memory WebSocket peer for connection lifecycle tests."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _ConnectionBuffers:
    client_outbox: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    server_outbox: asyncio.Queue[str | None] = field(default_factory=asyncio.Queue)
    closed: bool = False


class FakeClientConnection:
    def __init__(self, buffers: _ConnectionBuffers) -> None:
        self._buffers = buffers

    async def send(self, text: str) -> None:
        await self._buffers.client_outbox.put(text)

    async def close(self) -> None:
        if self._buffers.closed:
            return
        self._buffers.closed = True
        await self._buffers.server_outbox.put(None)

    async def ping(self) -> None:
        pass

    def __aiter__(self) -> "FakeClientConnection":
        return self

    async def __anext__(self) -> str:
        item = await self._buffers.server_outbox.get()
        if item is None:
            self._buffers.closed = True
            raise StopAsyncIteration
        return item


class FakeClawChatServer:
    def __init__(self) -> None:
        self._connections: list[_ConnectionBuffers] = []
        self._connect_log: list[dict[str, Any]] = []
        self._auto_fail = False

    def _buffers_for(self, connection_index: int = -1) -> _ConnectionBuffers:
        if not self._connections:
            raise RuntimeError("no fake websocket connection established")
        return self._connections[connection_index]

    def enqueue_from_server(self, frame: dict[str, Any], *, connection_index: int = -1) -> None:
        self._buffers_for(connection_index).server_outbox.put_nowait(json.dumps(frame))

    async def read_client_frame(
        self,
        timeout: float = 1.0,
        *,
        connection_index: int = -1,
    ) -> dict[str, Any]:
        raw = await asyncio.wait_for(
            self._buffers_for(connection_index).client_outbox.get(),
            timeout=timeout,
        )
        return json.loads(raw)

    async def disconnect(self, *, connection_index: int = -1) -> None:
        buffers = self._buffers_for(connection_index)
        if buffers.closed:
            return
        buffers.closed = True
        await buffers.server_outbox.put(None)

    async def connect(self, url: str, **kwargs: Any) -> FakeClientConnection:
        self._connect_log.append({"url": url, "kwargs": kwargs})
        if self._auto_fail:
            raise ConnectionError("fake auto-fail")
        buffers = _ConnectionBuffers()
        self._connections.append(buffers)
        return FakeClientConnection(buffers)

    def set_auto_fail(self, value: bool) -> None:
        self._auto_fail = value

    @property
    def connect_calls(self) -> list[dict[str, Any]]:
        return list(self._connect_log)
