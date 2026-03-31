from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from obsidian_ai.bot import is_allowed_webhook_message
from obsidian_ai.config import Settings


def build_settings() -> Settings:
    return Settings(
        discord_bot_token="token",
        discord_allowed_guild_ids=set(),
        discord_allowed_channel_ids=set(),
        discord_allowed_user_ids=set(),
        discord_allowed_webhook_ids={1488660901774102788},
        gemini_api_key="gemini",
        gemini_model="gemini-2.5-flash",
        obsidian_output_dir=Path("/tmp/obsidian-output"),
        state_path=Path("/tmp/processed_messages.json"),
        sync_state_path=Path("/tmp/pending_syncs.json"),
        static_tags=["inbox"],
        http_timeout_seconds=30,
        rclone_command="rclone",
        rclone_config_path=None,
        rclone_destination="icloud:Obsidian/inbox",
        rclone_sync_interval_seconds=300,
        rclone_sync_timeout_seconds=120,
    )


def test_allowed_webhook_message_requires_matching_allowlist_id() -> None:
    settings = build_settings()
    message = SimpleNamespace(webhook_id=1488660901774102788)
    assert is_allowed_webhook_message(message, settings) is True


def test_allowed_webhook_message_rejects_missing_and_non_matching_ids() -> None:
    settings = build_settings()
    no_webhook_message = SimpleNamespace(webhook_id=None)
    wrong_webhook_message = SimpleNamespace(webhook_id=99999)

    assert is_allowed_webhook_message(no_webhook_message, settings) is False
    assert is_allowed_webhook_message(wrong_webhook_message, settings) is False


def test_allowed_webhook_message_is_disabled_without_configured_ids() -> None:
    settings = replace(build_settings(), discord_allowed_webhook_ids=set())
    message = SimpleNamespace(webhook_id=1488660901774102788)
    assert is_allowed_webhook_message(message, settings) is False
