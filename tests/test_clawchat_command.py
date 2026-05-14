from __future__ import annotations

import asyncio

from clawchat_gateway.api_client import DEFAULT_BASE_URL
from clawchat_gateway.commands import handle_clawchat_activate_command


def test_handle_clawchat_activate_command_activates_and_reports_restart(monkeypatch) -> None:
    from clawchat_gateway import commands as command_mod

    calls = []

    async def fake_activate_and_maybe_restart(code: str, *, base_url: str, restart: bool):
        calls.append({"code": code, "base_url": base_url, "restart": restart})
        return {
            "user_id": "user-123",
            "restart_scheduled": True,
            "restart_delay_seconds": 2,
        }

    monkeypatch.setattr(
        command_mod,
        "activate_and_maybe_restart",
        fake_activate_and_maybe_restart,
    )

    result = asyncio.run(
        handle_clawchat_activate_command("ABC123 --base-url https://chat.example")
    )

    assert calls == [
        {"code": "ABC123", "base_url": "https://chat.example", "restart": True}
    ]
    assert result.splitlines() == [
        "clawchat: activation complete for user-123",
        "clawchat: Hermes restart scheduled in 2s",
    ]


def test_handle_clawchat_activate_command_honors_no_restart(monkeypatch) -> None:
    from clawchat_gateway import commands as command_mod

    calls = []

    async def fake_activate_and_maybe_restart(code: str, *, base_url: str, restart: bool):
        calls.append({"code": code, "base_url": base_url, "restart": restart})
        return {"user_id": "user-456"}

    monkeypatch.setattr(
        command_mod,
        "activate_and_maybe_restart",
        fake_activate_and_maybe_restart,
    )

    result = asyncio.run(handle_clawchat_activate_command("ABC123 --no-restart"))

    assert calls == [{"code": "ABC123", "base_url": DEFAULT_BASE_URL, "restart": False}]
    assert result == "clawchat: activation complete for user-456"


def test_handle_clawchat_activate_command_returns_usage_for_missing_code() -> None:
    result = asyncio.run(handle_clawchat_activate_command(""))

    assert "usage: /clawchat-activate CODE" in result
