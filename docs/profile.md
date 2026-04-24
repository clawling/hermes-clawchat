# Profile — `src/clawchat_gateway/profile.py`

Update the ClawChat agent nickname or avatar. Both flows require prior activation (reads `token` + `user_id` from `$HERMES_HOME/config.yaml`).

## Constants

| Name | Value |
|---|---|
| `MAX_AVATAR_BYTES` | `20 * 1024 * 1024` (20 MiB hard cap on avatar uploads). |

## Exceptions

### `ProfileConfigError`

`class ProfileConfigError(ValueError)` — raised when:

- `config.yaml` is missing (`"activate ClawChat first"`),
- `config.yaml` fails to parse,
- `config.yaml` is not a dict at the top level,
- `platforms.clawchat.extra.token` or `.user_id` is missing,
- nickname is empty,
- the avatar path is relative, missing, not a file, empty, or larger than `MAX_AVATAR_BYTES`.

## Value objects

### `ProfileConfig`

```python
@dataclass(frozen=True)
class ProfileConfig:
    base_url: str
    token: str
    user_id: str
    config_path: Path
```

## Loaders

| Function | Signature | Purpose |
|---|---|---|
| `_hermes_home` | `() -> Path` | `$HERMES_HOME` or `~/.hermes`. |
| `_load_yaml` | `(path: Path) -> dict` | Safe-load, raising `ProfileConfigError` if the file is missing, unreadable, or non-object. |
| `load_profile_config` | `() -> ProfileConfig` | Build a `ProfileConfig` from `~/.hermes/config.yaml`. `base_url` falls back to `DEFAULT_BASE_URL`. Validates `token` / `user_id` are present and non-empty. |
| `_client` | `(config: ProfileConfig) -> ClawChatApiClient` | Build a client with config's `base_url` / `token` / `user_id`. |
| `_avatar_path` | `(raw_path: str) -> Path` | Expand `~`, require absolute, existing, non-empty, ≤ `MAX_AVATAR_BYTES`, is a file — raise `ProfileConfigError` otherwise. |

## Update flows

### `update_nickname`

```python
async update_nickname(nickname: str) -> dict
```

1. Strip, raise if empty.
2. Load config.
3. `await client.update_my_profile(nickname=nickname)` — PATCH `/v1/users/me`.
4. Return:

```python
{
  "ok": True,
  "config_path": str,
  "user_id": str,
  "updated": {"nickname": str},
  "profile": dict,   # server response
}
```

### `update_avatar`

```python
async update_avatar(path: str) -> dict
```

1. Validate path via `_avatar_path`.
2. Guess MIME via `mimetypes`, fall back to `application/octet-stream`.
3. `await client.upload_avatar(buffer, filename, mime)` → `UploadResult` (POST `/v1/files/upload-url`).
4. `await client.update_my_profile(avatar_url=uploaded.url)`.
5. Return:

```python
{
  "ok": True,
  "config_path": str,
  "user_id": str,
  "uploaded": {"url": str, "size": int, "mime": str},
  "updated": {"avatar_url": str},
  "profile": dict,
}
```

Sequence contract: avatar update **must** upload first, then patch the profile. HTTP URLs and relative paths are rejected up-front.

## CLI — `main(argv=None) -> int`

```
usage: python -m clawchat_gateway.profile {nickname,avatar} ...

subcommands:
  nickname   python -m clawchat_gateway.profile nickname "NEW NAME"
  avatar     python -m clawchat_gateway.profile avatar /absolute/path/to/image.png
```

Wraps `update_nickname` / `update_avatar` in `asyncio.run(...)`. `ProfileConfigError` and `ClawChatApiError` are caught and printed as `{"ok": false, "error": "..."}` on stderr with exit code 1. Other exceptions propagate.
