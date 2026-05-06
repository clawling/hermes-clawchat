from __future__ import annotations


def compute_delta(previous: str, current: str) -> tuple[str, str]:
    if current.startswith(previous):
        return current, current[len(previous) :]
    return current, current
