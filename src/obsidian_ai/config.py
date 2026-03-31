from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _parse_int_set(name: str) -> set[int]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return set()
    values = set()
    for chunk in raw_value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.add(int(chunk))
    return values


def _parse_string_list(name: str, default: list[str] | None = None) -> list[str]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return list(default or [])
    return [item.strip() for item in raw_value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    discord_bot_token: str
    discord_allowed_guild_ids: set[int]
    discord_allowed_channel_ids: set[int]
    discord_allowed_user_ids: set[int]
    discord_allowed_webhook_ids: set[int]
    gemini_api_key: str
    gemini_model: str
    obsidian_output_dir: Path
    state_path: Path
    sync_state_path: Path
    static_tags: list[str]
    http_timeout_seconds: float
    rclone_command: str
    rclone_config_path: Path | None
    rclone_destination: str
    rclone_sync_interval_seconds: float
    rclone_sync_timeout_seconds: float


def load_settings() -> Settings:
    load_dotenv()

    discord_bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "").strip()
    obsidian_output_dir_raw = os.getenv("OBSIDIAN_OUTPUT_DIR", "").strip()
    rclone_destination = os.getenv("RCLONE_DESTINATION", "").strip()

    missing = []
    if not discord_bot_token:
        missing.append("DISCORD_BOT_TOKEN")
    if not gemini_api_key:
        missing.append("GEMINI_API_KEY")
    if not gemini_model:
        missing.append("GEMINI_MODEL")
    if not obsidian_output_dir_raw:
        missing.append("OBSIDIAN_OUTPUT_DIR")
    if not rclone_destination:
        missing.append("RCLONE_DESTINATION")

    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required environment variables: {joined}")

    state_path = Path(os.getenv("STATE_PATH", ".state/processed_messages.json")).expanduser()
    sync_state_path = Path(os.getenv("SYNC_STATE_PATH", ".state/pending_syncs.json")).expanduser()
    rclone_config_raw = os.getenv("RCLONE_CONFIG_PATH", "").strip()
    return Settings(
        discord_bot_token=discord_bot_token,
        discord_allowed_guild_ids=_parse_int_set("DISCORD_ALLOWED_GUILD_IDS"),
        discord_allowed_channel_ids=_parse_int_set("DISCORD_ALLOWED_CHANNEL_IDS"),
        discord_allowed_user_ids=_parse_int_set("DISCORD_ALLOWED_USER_IDS"),
        discord_allowed_webhook_ids=_parse_int_set("DISCORD_ALLOWED_WEBHOOK_IDS"),
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        obsidian_output_dir=Path(obsidian_output_dir_raw).expanduser(),
        state_path=state_path,
        sync_state_path=sync_state_path,
        static_tags=_parse_string_list("STATIC_TAGS", default=["inbox", "discord-capture"]),
        http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
        rclone_command=os.getenv("RCLONE_COMMAND", "rclone").strip() or "rclone",
        rclone_config_path=Path(rclone_config_raw).expanduser() if rclone_config_raw else None,
        rclone_destination=rclone_destination.rstrip("/"),
        rclone_sync_interval_seconds=float(os.getenv("RCLONE_SYNC_INTERVAL_SECONDS", "300")),
        rclone_sync_timeout_seconds=float(os.getenv("RCLONE_SYNC_TIMEOUT_SECONDS", "120")),
    )
