"""In-memory WebSocket peer for connection lifecycle tests."""

from __future__ import annotations

import asyncio
import json
from typing import Any


class FakeClientConnection:
    def __init__(self, server: "FakeClawChatServer") -> None:
        self._server = server

    async def send(self, text: str) -> None:
        await self._server._client_outbox.put(text)

    async def close(self) -> None:
        await self._server._server_outbox.put(None)

    async def ping(self) -> None:
        pass

    def __aiter__(self) -> "FakeClientConnection":
        return self

    async def __anext__(self) -> str:
        item = await self._server._server_outbox.get()
        if item is None:
            raise StopAsyncIteration
        return item


class FakeClawChatServer:
    def __init__(self) -> None:
        self._client_outbox: asyncio.Queue[str] = asyncio.Queue()
        self._server_outbox: asyncio.Queue[str | None] = asyncio.Queue()
        self._connect_log: list[dict[str, Any]] = []
        self._auto_fail = False

    def enqueue_from_server(self, frame: dict[str, Any]) -> None:
        self._server_outbox.put_nowait(json.dumps(frame))

    async def read_client_frame(self, timeout: float = 1.0) -> dict[str, Any]:
        raw = await asyncio.wait_for(self._client_outbox.get(), timeout=timeout)
        return json.loads(raw)

    async def disconnect(self) -> None:
        await self._server_outbox.put(None)

    async def connect(self, url: str, **kwargs: Any) -> FakeClientConnection:
        self._connect_log.append({"url": url, "kwargs": kwargs})
        if self._auto_fail:
            raise ConnectionError("fake auto-fail")
        return FakeClientConnection(self)

    def set_auto_fail(self, value: bool) -> None:
        self._auto_fail = value

    @property
    def connect_calls(self) -> list[dict[str, Any]]:
        return list(self._connect_log)
