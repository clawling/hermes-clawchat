from __future__ import annotations

import json

import pytest
import yaml

from clawchat_gateway.profile import ProfileConfigError, load_profile_config, main


def _write_config(home, *, token="tk", user_id="u1", base_url="http://127.0.0.1:1"):
    extra = {"base_url": base_url}
    if token:
        extra["token"] = token
    if user_id:
        extra["user_id"] = user_id
    (home / "config.yaml").write_text(
        yaml.safe_dump({"platforms": {"clawchat": {"extra": extra}}}),
        encoding="utf-8",
    )


def _write_env(home, **values):
    (home / ".env").write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()),
        encoding="utf-8",
    )


def test_load_profile_config_reads_token_from_env_file(monkeypatch, tmp_path):
    _write_config(tmp_path, token="")
    _write_env(tmp_path, CLAWCHAT_TOKEN="env-token")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    config = load_profile_config()

    assert config.token == "env-token"
    assert config.user_id == "u1"


def test_load_profile_config_prefers_process_env_over_env_file(monkeypatch, tmp_path):
    _write_config(tmp_path, token="")
    _write_env(tmp_path, CLAWCHAT_TOKEN="file-token")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("CLAWCHAT_TOKEN", "process-token")

    config = load_profile_config()

    assert config.token == "process-token"


def test_load_profile_config_requires_token(monkeypatch, tmp_path):
    _write_config(tmp_path, token="")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with pytest.raises(ProfileConfigError, match="token"):
        load_profile_config()


def test_load_profile_config_requires_user_id(monkeypatch, tmp_path):
    _write_config(tmp_path, user_id="")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    with pytest.raises(ProfileConfigError, match="user_id"):
        load_profile_config()


def test_cli_get_calls_handler_and_emits_json(monkeypatch, tmp_path, capsys):
    _write_config(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    async def fake_get_account_profile():
        return {"id": "u1", "nickname": "Alice"}

    from clawchat_gateway import tools

    monkeypatch.setattr(tools, "get_account_profile", fake_get_account_profile)

    rc = main(["get"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"id": "u1", "nickname": "Alice"}


def test_cli_update_emits_validation_error_to_stderr(monkeypatch, tmp_path, capsys):
    _write_config(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    rc = main(["update"])
    assert rc == 1
    captured = capsys.readouterr()
    err = json.loads(captured.err)
    assert err["error"] == "validation"
    assert captured.out == ""


def test_cli_upload_avatar_relative_path_emits_validation(monkeypatch, tmp_path, capsys):
    _write_config(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "rel.png").write_bytes(b"x")

    rc = main(["upload-avatar", "rel.png"])
    assert rc == 1
    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "validation"


def test_cli_friends_passes_pagination(monkeypatch, tmp_path, capsys):
    _write_config(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    seen = {}

    async def fake_list(page=None, page_size=None):
        seen["page"] = page
        seen["page_size"] = page_size
        return {"items": [], "page": page, "pageSize": page_size}

    from clawchat_gateway import tools

    monkeypatch.setattr(tools, "list_account_friends", fake_list)

    rc = main(["friends", "--page", "2", "--page-size", "50"])
    assert rc == 0
    assert seen == {"page": 2, "page_size": 50}
