# ClawChat Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python ClawChat v2 gateway adapter for hermes-agent that handles the main chat protocol path: handshake, inbound `message.send`, outbound static/stream replies, group routing, reply context, and media.

**Architecture:** The package mirrors the proven `packages/hermes/clawling` layout: pure protocol/config/inbound/media helpers in `src/clawchat_gateway/`, a reconnecting WebSocket lifecycle in `connection.py`, and a `BasePlatformAdapter` subclass in `adapter.py`. Tests use the same hermes stub strategy as `packages/hermes/clawling/tests/fake_hermes.py`, plus a fake WebSocket peer and mocked HTTP uploads/downloads.

**Tech Stack:** Python 3.11, `setuptools`, `websockets`, `urllib`/stdlib HTTP helpers, `pytest`, `pytest-asyncio`

---

## File Structure

**Create:**
- `pyproject.toml`
- `src/clawchat_gateway/__init__.py`
- `src/clawchat_gateway/config.py`
- `src/clawchat_gateway/protocol.py`
- `src/clawchat_gateway/inbound.py`
- `src/clawchat_gateway/media_runtime.py`
- `src/clawchat_gateway/stream_buffer.py`
- `src/clawchat_gateway/connection.py`
- `src/clawchat_gateway/adapter.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/fake_hermes.py`
- `tests/fake_ws.py`
- `tests/test_config.py`
- `tests/test_protocol.py`
- `tests/test_inbound.py`
- `tests/test_media_runtime.py`
- `tests/test_connection.py`
- `tests/test_adapter.py`

**Reference-only reads during implementation:**
- `../clawling/src/clawling_channel/config.py`
- `../clawling/src/clawling_channel/protocol.py`
- `../clawling/src/clawling_channel/connection.py`
- `../clawling/src/clawling_channel/adapter.py`
- `/Users/ivanlam/Projects/纽贝科技/助手/packages/openclaw-clawchat/src/protocol.ts`
- `/Users/ivanlam/Projects/纽贝科技/助手/packages/openclaw-clawchat/src/inbound.ts`
- `/Users/ivanlam/Projects/纽贝科技/助手/packages/openclaw-clawchat/src/outbound.ts`
- `/Users/ivanlam/Projects/纽贝科技/助手/packages/openclaw-clawchat/src/client.ts`
- `/Users/ivanlam/Projects/纽贝科技/助手/packages/openclaw-clawchat/src/streaming.ts`
- `/Users/ivanlam/Projects/纽贝科技/助手/packages/openclaw-clawchat/src/media-runtime.ts`
- `/Users/ivanlam/Projects/纽贝科技/助手/packages/openclaw-clawchat/src/*.test.ts`

### Task 1: Scaffold Package And Test Harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/clawchat_gateway/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fake_hermes.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing scaffold test**

```python
from clawchat_gateway import __version__


def test_package_imports():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_package_imports -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'clawchat_gateway'`

- [ ] **Step 3: Write minimal package and test harness**

`pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "clawchat-gateway"
version = "0.1.0"
description = "ClawChat v2 gateway adapter for hermes-agent"
requires-python = ">=3.11"
dependencies = ["websockets>=12,<16"]

[project.optional-dependencies]
test = ["pytest>=8", "pytest-asyncio>=0.23", "pytest-cov>=4"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-q"
```

`src/clawchat_gateway/__init__.py`

```python
__version__ = "0.1.0"
```

`tests/conftest.py`

```python
import sys
from pathlib import Path

_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tests.fake_hermes import install as _install_hermes_stubs

_install_hermes_stubs()
```

`tests/fake_hermes.py`

```python
from ../clawling/tests/fake_hermes import install  # copy the file locally, do not import relatively at runtime
```

Implementation note:
- Copy `../clawling/tests/fake_hermes.py` into `tests/fake_hermes.py`
- Extend `_Platform` with `CLAWCHAT = "clawchat"`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_package_imports -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/clawchat_gateway/__init__.py tests/__init__.py tests/conftest.py tests/fake_hermes.py tests/test_config.py
git commit -m "chore(clawchat): scaffold package and hermes test harness"
```

### Task 2: Config Parsing

**Files:**
- Create: `src/clawchat_gateway/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing config tests**

```python
from clawchat_gateway.config import ClawChatConfig


def test_config_defaults():
    cfg = ClawChatConfig.from_platform_config(type("PC", (), {"extra": {
        "websocket_url": "wss://chat.example/ws",
        "token": "tok",
        "user_id": "u1",
    }})())
    assert cfg.reply_mode == "static"
    assert cfg.group_mode == "mention"
    assert cfg.stream_flush_interval_ms == 250
    assert cfg.stream_min_chunk_chars == 40
    assert cfg.stream_max_buffer_chars == 2000


def test_config_accepts_nested_openclaw_names():
    cfg = ClawChatConfig.from_platform_config(type("PC", (), {"extra": {
        "websocketUrl": "wss://chat.example/ws",
        "baseUrl": "https://api.example",
        "token": "tok",
        "userId": "u1",
        "replyMode": "stream",
        "groupMode": "all",
        "stream": {"flushIntervalMs": 100, "minChunkChars": 8, "maxBufferChars": 512},
    }})())
    assert cfg.reply_mode == "stream"
    assert cfg.group_mode == "all"
    assert cfg.stream_flush_interval_ms == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -q`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `clawchat_gateway.config`

- [ ] **Step 3: Write minimal implementation**

`src/clawchat_gateway/config.py`

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ClawChatConfig:
    websocket_url: str
    base_url: str = ""
    token: str = ""
    user_id: str = ""
    reply_mode: str = "static"
    group_mode: str = "mention"
    stream_flush_interval_ms: int = 250
    stream_min_chunk_chars: int = 40
    stream_max_buffer_chars: int = 2000
    reconnect_initial_delay_ms: int = 500
    reconnect_max_delay_ms: int = 15000
    reconnect_jitter_ratio: float = 0.3
    reconnect_max_retries: float = float("inf")
    heartbeat_interval_ms: int = 20000
    heartbeat_timeout_ms: int = 10000
    ack_timeout_ms: int = 15000
    ack_auto_resend_on_timeout: bool = False
    media_local_roots: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_platform_config(cls, platform_config: Any) -> "ClawChatConfig":
        extra = getattr(platform_config, "extra", None) or {}
        stream = extra.get("stream") or {}
        return cls(
            websocket_url=extra.get("websocket_url") or extra.get("websocketUrl") or "",
            base_url=extra.get("base_url") or extra.get("baseUrl") or "",
            token=extra.get("token") or "",
            user_id=extra.get("user_id") or extra.get("userId") or "",
            reply_mode=extra.get("reply_mode") or extra.get("replyMode") or "static",
            group_mode=extra.get("group_mode") or extra.get("groupMode") or "mention",
            stream_flush_interval_ms=stream.get("flushIntervalMs", 250),
            stream_min_chunk_chars=stream.get("minChunkChars", 40),
            stream_max_buffer_chars=stream.get("maxBufferChars", 2000),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawchat_gateway/config.py tests/test_config.py
git commit -m "feat(clawchat): parse gateway config"
```

### Task 3: Protocol Layer

**Files:**
- Create: `src/clawchat_gateway/protocol.py`
- Modify: `tests/test_protocol.py`

- [ ] **Step 1: Write the failing protocol tests**

```python
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
    env = build_message_add_event(chat_id="c1", chat_type="direct", message_id="m1", full_text="hello", delta="lo")
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_protocol.py -q`
Expected: FAIL with missing imports from `clawchat_gateway.protocol`

- [ ] **Step 3: Write minimal implementation**

`src/clawchat_gateway/protocol.py`

```python
from __future__ import annotations

import hashlib
import hmac
import itertools
import json
from typing import Any

_counter = itertools.count(1)


def new_frame_id(prefix: str = "req") -> str:
    return f"{prefix}-{next(_counter)}"


def encode_frame(frame: dict[str, Any]) -> str:
    return json.dumps(frame, separators=(",", ":"), ensure_ascii=False)


def decode_frame(text: str) -> dict[str, Any]:
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("frame must be object")
    return obj


def compute_client_sign(client_id: str, nonce: str, token: str) -> str:
    return hmac.new(token.encode("utf-8"), f"{client_id}|{nonce}".encode("utf-8"), hashlib.sha256).hexdigest()


def extract_nonce(frame: dict[str, Any]) -> str | None:
    payload = frame.get("payload") or {}
    if isinstance(payload.get("nonce"), str):
        return payload["nonce"]
    data = payload.get("data") or {}
    if isinstance(data.get("nonce"), str):
        return data["nonce"]
    return None


def is_hello_ok(frame: dict[str, Any], expected_request_id: str) -> bool:
    return frame.get("type") == "res" and frame.get("requestId") == expected_request_id and (frame.get("payload") or {}).get("type") == "hello-ok"


def build_connect_request(*, frame_id: str, token: str, client_id: str, client_version: str, sign: str) -> dict[str, Any]:
    return {
        "type": "req",
        "id": frame_id,
        "method": "connect",
        "params": {"auth": {"token": token}, "client": {"id": client_id, "version": client_version, "sign": sign}},
    }


def _message_envelope(event: str, *, chat_id: str, chat_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": "event", "id": new_frame_id("evt"), "event": event, "chat_id": chat_id, "chat_type": chat_type, "payload": payload}


def build_message_created_event(*, chat_id: str, chat_type: str, message_id: str) -> dict[str, Any]:
    return _message_envelope("message.created", chat_id=chat_id, chat_type=chat_type, payload={"message": {"id": message_id}})


def build_message_add_event(*, chat_id: str, chat_type: str, message_id: str, full_text: str, delta: str) -> dict[str, Any]:
    return _message_envelope("message.add", chat_id=chat_id, chat_type=chat_type, payload={"message": {"id": message_id, "fragments": [{"kind": "text", "text": full_text, "delta": delta}]}})


def build_message_done_event(*, chat_id: str, chat_type: str, message_id: str) -> dict[str, Any]:
    return _message_envelope("message.done", chat_id=chat_id, chat_type=chat_type, payload={"message": {"id": message_id}})


def build_message_reply_event(*, chat_id: str, chat_type: str, fragments: list[dict[str, Any]], reply_to_message_id: str | None = None) -> dict[str, Any]:
    context = {}
    if reply_to_message_id:
        context["reply_to_message_id"] = reply_to_message_id
    return _message_envelope("message.reply", chat_id=chat_id, chat_type=chat_type, payload={"message": {"fragments": fragments, "context": context}})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_protocol.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawchat_gateway/protocol.py tests/test_protocol.py
git commit -m "feat(clawchat): add protocol builders and handshake helpers"
```

### Task 4: Inbound Mapping

**Files:**
- Create: `src/clawchat_gateway/inbound.py`
- Modify: `tests/test_inbound.py`

- [ ] **Step 1: Write the failing inbound tests**

```python
from clawchat_gateway.inbound import parse_inbound_message
from clawchat_gateway.config import ClawChatConfig


def test_group_message_requires_mention_in_mention_mode():
    cfg = ClawChatConfig(websocket_url="wss://x", token="t", user_id="bot", group_mode="mention")
    env = {
        "chat_id": "g1",
        "chat_type": "group",
        "sender": {"id": "u1", "nick_name": "alice"},
        "payload": {"message": {"fragments": [{"kind": "text", "text": "hello"}], "context": {"mentions": [{"id": "other"}]}}},
    }
    inbound = parse_inbound_message(env, cfg)
    assert inbound is None


def test_reply_preview_is_preserved():
    cfg = ClawChatConfig(websocket_url="wss://x", token="t", user_id="bot")
    env = {
        "chat_id": "u1",
        "chat_type": "direct",
        "sender": {"id": "u1", "nick_name": "alice"},
        "payload": {"message": {"fragments": [{"kind": "text", "text": "hello"}], "context": {"reply": {"id": "u2", "nick_name": "bob", "fragments": [{"kind": "text", "text": "old"}]}}}},
    }
    inbound = parse_inbound_message(env, cfg)
    assert inbound.reply_preview["id"] == "u2"
    assert inbound.text == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_inbound.py -q`
Expected: FAIL with missing `parse_inbound_message`

- [ ] **Step 3: Write minimal implementation**

`src/clawchat_gateway/inbound.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clawchat_gateway.config import ClawChatConfig


@dataclass(frozen=True)
class InboundMessage:
    chat_id: str
    chat_type: str
    sender_id: str
    sender_name: str
    text: str
    raw_message: dict[str, Any]
    reply_preview: dict[str, Any] | None = None
    media_urls: list[str] = field(default_factory=list)


def parse_inbound_message(envelope: dict[str, Any], config: ClawChatConfig) -> InboundMessage | None:
    payload = envelope.get("payload") or {}
    message = payload.get("message") or {}
    context = message.get("context") or {}
    chat_type = envelope.get("chat_type") or "direct"
    if chat_type == "group" and config.group_mode == "mention":
        mentions = context.get("mentions") or []
        if not any(m.get("id") == config.user_id for m in mentions if isinstance(m, dict)):
            return None

    fragments = message.get("fragments") or []
    text_parts = []
    media_urls = []
    for frag in fragments:
        kind = frag.get("kind")
        if kind == "text" and isinstance(frag.get("text"), str):
            text_parts.append(frag["text"])
        elif kind in {"image", "file", "audio", "video"} and isinstance(frag.get("url"), str):
            media_urls.append(frag["url"])
            label = frag.get("name") or frag["url"]
            if kind == "image":
                text_parts.append(f"![{label}]({frag['url']})")
            else:
                text_parts.append(f"[{label}]({frag['url']})")

    sender = envelope.get("sender") or {}
    return InboundMessage(
        chat_id=envelope.get("chat_id") or "",
        chat_type=chat_type,
        sender_id=sender.get("id") or "",
        sender_name=sender.get("nick_name") or "",
        text="\n".join(p for p in text_parts if p),
        raw_message=envelope,
        reply_preview=context.get("reply"),
        media_urls=media_urls,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_inbound.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawchat_gateway/inbound.py tests/test_inbound.py
git commit -m "feat(clawchat): map inbound message.send envelopes"
```

### Task 5: Media Runtime

**Files:**
- Create: `src/clawchat_gateway/media_runtime.py`
- Modify: `tests/test_media_runtime.py`

- [ ] **Step 1: Write the failing media tests**

```python
from pathlib import Path

import pytest

from clawchat_gateway.media_runtime import ensure_allowed_local_path, infer_media_kind_from_mime


def test_infer_media_kind_from_mime():
    assert infer_media_kind_from_mime("image/png") == "image"
    assert infer_media_kind_from_mime("audio/mpeg") == "audio"
    assert infer_media_kind_from_mime("video/mp4") == "video"
    assert infer_media_kind_from_mime("application/pdf") == "file"


def test_local_path_must_be_under_allowed_roots(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "a.txt"
    inside.write_text("x")
    assert ensure_allowed_local_path(str(inside), [str(allowed)]) == inside
    with pytest.raises(ValueError):
        ensure_allowed_local_path("/tmp/outside.txt", [str(allowed)])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_media_runtime.py -q`
Expected: FAIL with missing imports from `media_runtime`

- [ ] **Step 3: Write minimal implementation**

`src/clawchat_gateway/media_runtime.py`

```python
from __future__ import annotations

from pathlib import Path


def infer_media_kind_from_mime(mime: str) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "file"


def ensure_allowed_local_path(path: str, allowed_roots: list[str]) -> Path:
    resolved = Path(path).expanduser().resolve()
    roots = [Path(root).expanduser().resolve() for root in allowed_roots]
    if roots and not any(root == resolved or root in resolved.parents for root in roots):
        raise ValueError(f"path not under allowed roots: {resolved}")
    return resolved
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_media_runtime.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawchat_gateway/media_runtime.py tests/test_media_runtime.py
git commit -m "feat(clawchat): add media path and mime helpers"
```

### Task 6: WebSocket Connection Lifecycle

**Files:**
- Create: `src/clawchat_gateway/connection.py`
- Create: `tests/fake_ws.py`
- Modify: `tests/test_connection.py`

- [ ] **Step 1: Write the failing connection tests**

```python
import asyncio

from clawchat_gateway.config import ClawChatConfig
from clawchat_gateway.connection import ClawChatConnection

from tests.fake_ws import FakeClawChatServer


async def test_handshake_reaches_ready(monkeypatch):
    srv = FakeClawChatServer()
    monkeypatch.setattr("clawchat_gateway.connection._ws_connect", srv.connect)
    seen = []

    async def on_message(_frame): pass
    async def on_state(state): seen.append(state)

    conn = ClawChatConnection(
        ClawChatConfig(websocket_url="ws://fake", token="tok", user_id="bot"),
        on_message=on_message,
        on_state_change=on_state,
    )
    await conn.start()
    try:
        srv.enqueue_from_server({"type": "event", "id": "e1", "event": "connect.challenge", "payload": {"nonce": "N"}})
        req = await srv.read_client_frame(timeout=1.0)
        assert req["method"] == "connect"
        srv.enqueue_from_server({"type": "res", "id": "r1", "requestId": req["id"], "payload": {"type": "hello-ok"}})
        for _ in range(20):
            if conn.is_ready:
                break
            await asyncio.sleep(0.01)
        assert conn.is_ready is True
        assert "ready" in [s.value for s in seen]
    finally:
        await conn.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_connection.py::test_handshake_reaches_ready -q`
Expected: FAIL with missing `ClawChatConnection`

- [ ] **Step 3: Write minimal implementation**

Implementation:
- Copy `../clawling/tests/fake_ws.py` into `tests/fake_ws.py`
- Rename its public class to `FakeClawChatServer`
- Copy `../clawling/src/clawling_channel/connection.py` into `src/clawchat_gateway/connection.py`
- Rename symbols:
  - `ClawlingConnection` -> `ClawChatConnection`
  - `ClawlingConfig` -> `ClawChatConfig`
  - `OnChatSend` -> `OnMessage`
- Replace inbound `chat.send` dispatch with generic `message.send` dispatch:

```python
if ftype == "event" and frame.get("event") == "message.send":
    await self._on_message(frame)
    return
```

- Keep these behaviors from the copied file:
  - handshake timeout
  - send queue before ready
  - exponential backoff
  - Bearer auth header
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_connection.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawchat_gateway/connection.py tests/fake_ws.py tests/test_connection.py
git commit -m "feat(clawchat): add websocket connection lifecycle"
```

### Task 7: Stream Buffer

**Files:**
- Create: `src/clawchat_gateway/stream_buffer.py`
- Modify: `tests/test_adapter.py`

- [ ] **Step 1: Write the failing stream buffer tests**

```python
from clawchat_gateway.stream_buffer import compute_delta


def test_compute_delta_uses_suffix_when_content_extends():
    full, delta = compute_delta("abc", "abcdef")
    assert full == "abcdef"
    assert delta == "def"


def test_compute_delta_falls_back_to_full_on_prefix_reset():
    full, delta = compute_delta("abcdef", "xyz")
    assert full == "xyz"
    assert delta == "xyz"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapter.py::test_compute_delta_uses_suffix_when_content_extends -q`
Expected: FAIL with missing `stream_buffer`

- [ ] **Step 3: Write minimal implementation**

`src/clawchat_gateway/stream_buffer.py`

```python
def compute_delta(previous: str, current: str) -> tuple[str, str]:
    if current.startswith(previous):
        return current, current[len(previous):]
    return current, current
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_adapter.py::test_compute_delta_uses_suffix_when_content_extends tests/test_adapter.py::test_compute_delta_falls_back_to_full_on_prefix_reset -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawchat_gateway/stream_buffer.py tests/test_adapter.py
git commit -m "feat(clawchat): add stream delta helper"
```

### Task 8: Adapter Integration

**Files:**
- Create: `src/clawchat_gateway/adapter.py`
- Modify: `tests/test_adapter.py`

- [ ] **Step 1: Write the failing adapter tests**

```python
from clawchat_gateway.adapter import ClawChatAdapter
from clawchat_gateway.inbound import InboundMessage


async def test_on_message_builds_message_event(monkeypatch):
    class FakeConnection:
        async def start(self): pass
        async def stop(self): pass
        async def send_frame(self, frame): self.last = frame

    from types import SimpleNamespace
    adapter = ClawChatAdapter(SimpleNamespace(extra={"websocket_url": "ws://x", "token": "t", "user_id": "bot"}))
    adapter._connection = FakeConnection()
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


async def test_send_emits_message_reply_for_static_mode(monkeypatch):
    sent = []

    class FakeConnection:
        async def start(self): pass
        async def stop(self): pass
        async def send_frame(self, frame): sent.append(frame)

    from types import SimpleNamespace
    adapter = ClawChatAdapter(SimpleNamespace(extra={"websocket_url": "ws://x", "token": "t", "user_id": "bot"}))
    adapter._connection = FakeConnection()
    result = await adapter.send(chat_id="u1", content="hi")
    assert result.success is True
    assert sent[0]["event"] == "message.reply"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapter.py -q`
Expected: FAIL with missing `ClawChatAdapter`

- [ ] **Step 3: Write minimal implementation**

Implementation:
- Copy `../clawling/src/clawling_channel/adapter.py` into `src/clawchat_gateway/adapter.py`
- Rename:
  - `ClawlingAdapter` -> `ClawChatAdapter`
  - `Platform.CLAWLING` -> `Platform.CLAWCHAT`
- Replace the event builders:
  - static `send()` uses `build_message_reply_event`
  - streaming `send()`/`edit_message()` use `build_message_created_event`, `build_message_add_event`, `build_message_done_event`
- Add an internal helper:

```python
async def _handle_inbound(self, inbound: InboundMessage) -> None:
    source = self.build_source(chat_id=inbound.chat_id, sender_id=inbound.sender_id, chat_name=inbound.chat_id)
    event = MessageEvent(
        text=inbound.text,
        message_type=MessageType.TEXT,
        source=source,
        raw_message={
            "clawchat_chat_type": inbound.chat_type,
            "clawchat_reply": inbound.reply_preview,
            "clawchat_raw": inbound.raw_message,
        },
        media_urls=inbound.media_urls,
    )
    await self.handle_message(event)
```

- Keep a small `_active_runs` map so:
  - first `send()` in stream mode emits `message.created`
  - `edit_message()` emits `message.add`
  - `on_run_complete()` emits `message.done` then consolidated `message.reply`
- Force static mode when outbound media exists
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_adapter.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawchat_gateway/adapter.py tests/test_adapter.py
git commit -m "feat(clawchat): add hermes adapter integration"
```

### Task 9: End-To-End Fake Integration And Docker Debug Script

**Files:**
- Modify: `tests/test_connection.py`
- Modify: `tests/test_adapter.py`
- Create: `docs/docker-debug.md`

- [ ] **Step 1: Write the failing integration test**

```python
async def test_end_to_end_message_send_to_stream_reply(monkeypatch):
    # Build a fake connection peer, push `message.send`, verify:
    # 1. adapter receives a handled MessageEvent
    # 2. adapter.send/edit_message/on_run_complete emit
    #    message.created -> message.add -> message.done -> message.reply
    assert False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapter.py::test_end_to_end_message_send_to_stream_reply -q`
Expected: FAIL on `assert False`

- [ ] **Step 3: Implement integration test and Docker debug notes**

Replace the placeholder test with a real one using `FakeClawChatServer` and the real adapter, asserting these ordered events:

```python
assert [frame["event"] for frame in sent_frames] == [
    "message.created",
    "message.add",
    "message.done",
    "message.reply",
]
```

Create `docs/docker-debug.md` with these exact commands:

```bash
cd /Users/ivanlam/Projects/纽贝科技/助手/hermes-agent
docker build -t hermes-agent:local .
docker run --rm -it \
  -v /Users/ivanlam/Projects/纽贝科技/助手/packages/hermes/clawchat:/opt/extensions/clawchat \
  hermes-agent:local
```

And include manual checks:
- WebSocket opens with `Authorization: Bearer <token>`
- server sends `connect.challenge`
- client returns `connect`
- `hello-ok` flips adapter ready state
- inbound `message.send` appears as Hermes `MessageEvent`
- stream mode yields `message.created/add/done/reply`
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_connection.py tests/test_adapter.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_connection.py tests/test_adapter.py docs/docker-debug.md
git commit -m "test(clawchat): add fake integration coverage and docker debug notes"
```

## Self-Review

### Spec Coverage

- Handshake: Task 3, Task 6
- Inbound `message.send`: Task 4, Task 8
- Direct/group/mention routing: Task 4
- Reply context: Task 4, Task 8
- Static reply: Task 3, Task 8
- Stream lifecycle: Task 3, Task 7, Task 8, Task 9
- Media helpers: Task 5
- Docker validation path: Task 9

No spec requirement is currently uncovered except real `/media/upload` HTTP wiring, which is intentionally reduced to path/mime helpers in this first plan. If real upload logic is required during implementation, add one follow-up task before claiming completion.

### Placeholder Scan

- Removed all `TODO`/`TBD` markers
- Replaced vague “add tests” statements with explicit tests and commands
- Replaced generic “implement connection” with exact copied baseline and rename targets

### Type Consistency

- Config type: `ClawChatConfig`
- Connection type: `ClawChatConnection`
- Adapter type: `ClawChatAdapter`
- Inbound parsed object: `InboundMessage`
- Completion hook name stays `on_run_complete`

