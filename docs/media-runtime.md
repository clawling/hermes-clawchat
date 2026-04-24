# Media Runtime — `src/clawchat_gateway/media_runtime.py`

Upload outbound media to ClawChat (`/media/upload`) and download inbound media into a local cache dir. All I/O is performed in threads via `asyncio.to_thread`.

## Value objects

### `UploadMediaResult`

```python
@dataclass(frozen=True)
class UploadMediaResult:
    url: str
    mime: str
    size: int
```

### `LoadedMedia`

```python
@dataclass(frozen=True)
class LoadedMedia:
    buffer: bytes
    filename: str
    mime: str
```

Produced by `_load_local_media` / `_load_remote_media`.

### `DownloadedMedia`

```python
@dataclass(frozen=True)
class DownloadedMedia:
    local_path: Path
    mime: str
    size: int
    source_url: str
```

## Classification & URL helpers

| Function | Signature | Purpose |
|---|---|---|
| `infer_media_kind_from_mime` | `(mime: str) -> str` | `"image" / "audio" / "video" / "file"` from a MIME prefix. |
| `derive_base_url` | `(*, websocket_url: str, base_url: str) -> str` | Prefer `websocket_url`'s host with `ws→http`/`wss→https`. If `ws` scheme is absent, fall back to `base_url`. Raises `ValueError` if both fail. |
| `_guess_mime` | `(filename: str, default="application/octet-stream") -> str` | `mimetypes.guess_type` wrapper. |
| `_is_remote_url` | `(value: str) -> bool` | `True` if scheme is `http` / `https`. |
| `_resolve_inbound_media_url` | `(url: str, *, base_url: str, websocket_url: str) -> str` | If already remote, return as-is. Otherwise join against `derive_base_url(...)`. |
| `_safe_download_filename` | `(url: str, mime: str) -> str` | Use the URL path basename; else construct `f"media-{uuid4hex}{guess_extension(mime) or '.bin'}"`. |

## Local-path guard

### `ensure_allowed_local_path(path: str, allowed_roots: Sequence[str]) -> Path`

Resolves `path` to an absolute `Path`, resolves every root, and requires the resolved path to be equal to or under one of the roots. Raises:

- `ValueError("no allowed roots configured")` when `allowed_roots` is empty.
- `ValueError("path not under allowed roots: ...")` otherwise.

This is enforced before reading any local file for upload, which is the path traversal guard for the outbound media flow.

## Local/remote loaders

| Function | Signature | Purpose |
|---|---|---|
| `_load_local_media` | `(path: str, media_local_roots: Sequence[str]) -> LoadedMedia` | Validate via `ensure_allowed_local_path`, read bytes, guess MIME. |
| `_load_remote_media` | `(url: str) -> LoadedMedia` | HTTP `urlopen`, read bytes, take `Content-Type` or guess from URL. |

## Download

### `_download_inbound_media_sync(*, url, token, download_dir: Path) -> DownloadedMedia`

HTTP GET with `Authorization: Bearer <token>` when token is set; saves to `<download_dir>/<uuid4hex>-<safe_filename>`; returns the full `DownloadedMedia`.

### `async download_inbound_media(urls, *, base_url, websocket_url, token, download_dir, download_file=None) -> list[DownloadedMedia]`

Loop over URLs, resolve via `_resolve_inbound_media_url`, run the (overridable) downloader in a thread. Exceptions per-URL are swallowed and the URL is skipped — callers see only the successful downloads.

Optional `download_file` hook lets tests inject a fake downloader.

## Upload

### `_encode_multipart(*, buffer, filename, mime) -> tuple[bytes, str]`

Builds a single-field `multipart/form-data` body (`name="file"`) and returns `(body, boundary)`.

### `_upload_media_sync(*, base_url, token, buffer, filename, mime) -> UploadMediaResult`

POSTs to `{base_url}/media/upload` with `Authorization: Bearer <token>`. Expects `{data: {url, mime, size?}}`; raises `ValueError` if `data` is missing or `url` / `mime` aren't strings.

### `async _upload_media(*, base_url, token, buffer, filename, mime) -> UploadMediaResult`

Thread wrapper around `_upload_media_sync`.

### `async upload_outbound_media(urls, *, base_url, websocket_url, token, media_local_roots, upload_file=None) -> list[dict[str, object]]`

For each URL:

1. Load from local (subject to `media_local_roots` guard) or remote.
2. Upload via the supplied `upload_file` (default `_upload_media`).
3. Emit a fragment dict:

```python
{
  "kind": infer_media_kind_from_mime(uploaded.mime),
  "url": uploaded.url,
  "mime": uploaded.mime,
  "size": uploaded.size,
  "name": loaded.filename,
}
```

Per-URL exceptions are swallowed (the URL is dropped from the result list). Returns `[]` when `urls` is empty.
