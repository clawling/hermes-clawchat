# Device ID — `src/clawchat_gateway/device_id.py`

Produces a stable `X-Device-Id` string for every outbound HTTP request and WebSocket handshake. Result is memoised via `functools.lru_cache(maxsize=1)`.

## Strategy (in priority order)

1. **Environment override.** `CLAWCHAT_DEVICE_ID` — used verbatim if it already starts with `hermes-`; otherwise sanitised through `_safe_id("hermes", ...)`.
2. **macOS IOPlatformUUID.** `ioreg -rd1 -c IOPlatformExpertDevice`, extract the `IOPlatformUUID` field, lowercased, prefixed `hermes-mac-`.
3. **Linux machine-id.** Hash the contents of `/etc/machine-id` or `/var/lib/dbus/machine-id` (SHA-256, first 24 hex chars) → `hermes-machine-<hash>`.
4. **Host fingerprint fallback.** SHA-256 of `f"{hostname}:{MAC_address_hex}"`, first 24 hex chars → `hermes-host-<hash>`.

## Functions

| Function | Signature | Purpose |
|---|---|---|
| `_safe_id` | `(prefix: str, value: str) -> str` | Collapse `[^A-Za-z0-9_.:-]+` to `-`, return `f"{prefix}-{clean}"` or `""` if clean is empty. |
| `_mac_platform_uuid` | `() -> str` | Run `ioreg` on Darwin with a 2s timeout, parse `IOPlatformUUID`, return `hermes-mac-<uuid>`. Returns `""` on any failure. |
| `_machine_id` | `() -> str` | Read one of the two D-Bus / systemd machine-id files, SHA-256, first 24 hex chars, `hermes-machine-<hash>`. Returns `""` if neither file is readable. |
| `_host_fingerprint` | `() -> str` | Always-available fallback: hash of hostname + MAC-derived `uuid.getnode()`. |
| `get_device_id` | `() -> str` | Cached public API: env override → mac → linux → host fallback. |

Stability goals: the same Hermes install should get the same device id across process restarts; distinct installs on the same machine can opt out of sharing via `CLAWCHAT_DEVICE_ID`.
