# hermes-clawchat — Code Reference

Per-module catalogue of structures and functions. For runtime flow and the boot sequence, see [architecture.md](./architecture.md).

## Index

| File | Purpose | Doc |
|---|---|---|
| `__init__.py` (repo root) | Hermes plugin entrypoint — registers tools + skill, auto-installs gateway | [plugin-entrypoint.md](./plugin-entrypoint.md) |
| `plugin.yaml` | Hermes plugin manifest | [plugin-entrypoint.md](./plugin-entrypoint.md) |
| `src/clawchat_gateway/__init__.py` | Package surface | [plugin-entrypoint.md](./plugin-entrypoint.md) |
| `src/clawchat_gateway/install.py` | Anchor-patch installer for hermes-agent | [installer.md](./installer.md) |
| `src/clawchat_gateway/adapter.py` | `ClawChatAdapter` — hermes-agent platform adapter | [adapter.md](./adapter.md) |
| `src/clawchat_gateway/connection.py` | WebSocket supervisor, handshake, send queue | [connection.md](./connection.md) |
| `src/clawchat_gateway/protocol.py` | Frame encode/decode + builder functions | [protocol.md](./protocol.md) |
| `src/clawchat_gateway/config.py` | `ClawChatConfig` dataclass | [config.md](./config.md) |
| `src/clawchat_gateway/api_client.py` | REST HTTP client (`ClawChatApiClient`) | [api-client.md](./api-client.md) |
| `src/clawchat_gateway/activate.py` | Activation CLI (`/v1/agents/connect`) | [activate.md](./activate.md) |
| `src/clawchat_gateway/profile.py` | Nickname / avatar CLI | [profile.md](./profile.md) |
| `src/clawchat_gateway/inbound.py` | Inbound WebSocket frame parser | [inbound.md](./inbound.md) |
| `src/clawchat_gateway/media_runtime.py` | Upload / download helpers + local-root guards | [media-runtime.md](./media-runtime.md) |
| `src/clawchat_gateway/stream_buffer.py` | `compute_delta` streaming helper | [stream-buffer.md](./stream-buffer.md) |
| `src/clawchat_gateway/device_id.py` | Stable `X-Device-Id` resolver | [device-id.md](./device-id.md) |
| `skills/clawchat/SKILL.md` | Hermes skill surfaced to the model | [skill.md](./skill.md) |
| `tests/` | Pytest suite and hermes-agent stubs | [tests.md](./tests.md) |
