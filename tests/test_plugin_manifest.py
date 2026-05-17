from pathlib import Path
import tomllib

import yaml


def test_plugin_manifest_declares_v012_platform_credentials():
    manifest = yaml.safe_load((Path(__file__).resolve().parents[1] / "plugin.yaml").read_text())

    assert manifest["kind"] == "platform"
    assert manifest["requires_env"] == ["CLAWCHAT_TOKEN", "CLAWCHAT_REFRESH_TOKEN"]
    assert manifest["provides_tools"] == [
        "clawchat_get_account_profile",
        "clawchat_get_user_profile",
        "clawchat_list_account_friends",
        "clawchat_search_users",
        "clawchat_list_moments",
        "clawchat_create_moment",
        "clawchat_delete_moment",
        "clawchat_toggle_moment_reaction",
        "clawchat_create_moment_comment",
        "clawchat_reply_moment_comment",
        "clawchat_delete_moment_comment",
        "clawchat_update_account_profile",
        "clawchat_upload_avatar_image",
        "clawchat_upload_media_file",
    ]


def test_bundled_skill_frontmatter_matches_hermes_authoring_rules():
    skill_path = Path(__file__).resolve().parents[1] / "skills" / "clawchat" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])

    assert frontmatter["name"] == "clawchat"
    assert frontmatter["description"] == "ClawChat profiles, friends, moments, and media."
    assert len(frontmatter["description"]) <= 60
    assert frontmatter["description"].endswith(".")


def test_bundled_skill_uses_modern_runtime_structure():
    skill_path = Path(__file__).resolve().parents[1] / "skills" / "clawchat" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")

    for heading in [
        "# ClawChat Skill",
        "## When to Use",
        "## Prerequisites",
        "## How to Run",
        "## Quick Reference",
        "## Procedure",
        "## Pitfalls",
        "## Verification",
    ]:
        assert heading in text

    assert "Profile edit request" in text
    assert "Update Hermes agent identity where supported" in text
    assert "Update ClawChat account profile where supported" in text
    assert "Ask only for the missing value" in text
    assert "clawchat:clawchat" not in text
    assert "$HERMES_HOME/skills" not in text


def test_package_exposes_no_legacy_anchor_patch_console_script():
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())

    assert pyproject["project"].get("scripts", {}) == {}
