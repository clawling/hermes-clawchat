# Stream Buffer — `src/clawchat_gateway/stream_buffer.py`

One small helper used by the adapter to emit streaming deltas.

## `compute_delta`

```python
def compute_delta(previous: str, current: str) -> tuple[str, str]:
    if current.startswith(previous):
        return current, current[len(previous):]
    return current, current
```

- **Prefix-extension case** (`current` is `previous` plus a suffix): returns `(current, appended_suffix)`. The adapter sends only the appended suffix as the `delta` in `message.add`.
- **Divergent case** (the model rewrote earlier text): returns `(current, current)`. The adapter emits the full new text as both `text` and `delta`, which tells the client to treat this as a replacement rather than a pure append.

This is the only piece of stream state that doesn't live in `_ActiveRun` — the adapter threads `previous` in as `run.last_text` and then writes the returned `current` back.
