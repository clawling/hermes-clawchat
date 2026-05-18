from __future__ import annotations

import sqlite3
from pathlib import Path

from clawchat_gateway.storage import ClawChatStore, default_db_path, json_dumps


def _rows(db_path: Path, sql: str, params: tuple = ()) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_default_db_path_uses_hermes_home_and_fixed_filename(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))

    assert default_db_path() == tmp_path / "hermes-home" / "clawchat.sqlite"


def test_json_dumps_is_stable_and_unicode() -> None:
    assert json_dumps({"b": 1, "a": "测试"}) == '{"a": "测试", "b": 1}'
    assert json_dumps(None) is None


def test_initialize_creates_schema_and_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "clawchat.sqlite"
    store = ClawChatStore(db_path)

    store.initialize()

    tables = {
        row[0]
        for row in _rows(
            db_path,
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        )
    }
    assert {
        "schema_migrations",
        "clawchat_messages",
        "activations",
        "connections",
        "tool_calls",
    }.issubset(tables)
    assert _rows(db_path, "SELECT version, name FROM schema_migrations") == [
        (1, "initial_schema")
    ]


def test_upsert_activation_keeps_latest_platform_account(tmp_path: Path) -> None:
    db_path = tmp_path / "clawchat.sqlite"
    store = ClawChatStore(db_path)

    store.upsert_activation(
        platform="hermes",
        account_id="default",
        user_id="user-1",
        access_token="token-old",
        refresh_token="refresh-old",
        activated_at=1000,
        updated_at=1000,
        login_method="unknown",
    )
    store.upsert_activation(
        platform="hermes",
        account_id="default",
        user_id="user-2",
        access_token="token-new",
        refresh_token=None,
        activated_at=2000,
        updated_at=2000,
        login_method="unknown",
    )

    rows = _rows(
        db_path,
        "SELECT user_id, access_token, refresh_token, activated_at, updated_at "
        "FROM activations WHERE platform = 'hermes' AND account_id = 'default'",
    )
    assert rows == [("user-2", "token-new", None, 2000, 2000)]


def test_insert_message_records_complete_message(tmp_path: Path) -> None:
    db_path = tmp_path / "clawchat.sqlite"
    store = ClawChatStore(db_path)

    store.insert_message(
        platform="hermes",
        account_id="default",
        kind="message",
        direction="inbound",
        event_type="message.send",
        trace_id="trace-1",
        chat_id="chat-1",
        message_id="msg-1",
        text="hello",
        raw={"event": "message.send"},
        created_at=1000,
    )

    row = _rows(
        db_path,
        "SELECT kind, direction, event_type, message_id, text FROM clawchat_messages",
    )[0]
    assert row == ("message", "inbound", "message.send", "msg-1", "hello")


def test_connection_lifecycle_updates_one_row(tmp_path: Path) -> None:
    db_path = tmp_path / "clawchat.sqlite"
    store = ClawChatStore(db_path)

    row_id = store.start_connection(
        platform="hermes",
        account_id="default",
        attempt=1,
        reconnect_count=0,
        connect_started_at=1000,
    )
    assert row_id is not None
    store.mark_connect_sent(row_id, connect_sent_at=1100)
    store.mark_connection_ready(row_id, ready_at=1200)
    store.finish_connection(
        row_id,
        state="disconnected",
        disconnected_at=1300,
        close_code=1006,
        close_reason="lost",
    )

    row = _rows(
        db_path,
        "SELECT state, connect_started_at, connect_sent_at, ready_at, "
        "disconnected_at, close_code, close_reason FROM connections",
    )[0]
    assert row == ("disconnected", 1000, 1100, 1200, 1300, 1006, "lost")


def test_record_tool_call_records_duration(tmp_path: Path) -> None:
    db_path = tmp_path / "clawchat.sqlite"
    store = ClawChatStore(db_path)

    store.record_tool_call(
        platform="hermes",
        account_id="default",
        tool_name="clawchat_get_account_profile",
        args={"a": 1},
        result={"ok": True},
        error=None,
        started_at=1000,
        ended_at=1250,
    )

    row = _rows(
        db_path,
        "SELECT tool_name, account_id, args_json, result_json, duration_ms FROM tool_calls",
    )[0]
    assert row[0] == "clawchat_get_account_profile"
    assert row[1] == "default"
    assert row[2] == '{"a": 1}'
    assert row[3] == '{"ok": true}'
    assert row[4] == 250
