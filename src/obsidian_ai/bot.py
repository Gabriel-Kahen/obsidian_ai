from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import discord
import httpx

from obsidian_ai.config import Settings, load_settings
from obsidian_ai.fetcher import fetch_source_context
from obsidian_ai.gemini import GeminiClient
from obsidian_ai.models import SourceContext
from obsidian_ai.pipelines import resolve_link_pipeline
from obsidian_ai.parsing import build_message_payload
from obsidian_ai.renderer import build_note_path, render_note
from obsidian_ai.state import PendingSyncStore, ProcessedMessageStore
from obsidian_ai.sync import RcloneSyncer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("obsidian_ai")


def is_allowed_webhook_message(message: discord.Message, settings: Settings) -> bool:
    return message.webhook_id is not None and message.webhook_id in settings.discord_allowed_webhook_ids


class DiscordObsidianClient(discord.Client):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.settings = settings
        self.store = ProcessedMessageStore(settings.state_path)
        self.gemini = GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.http_timeout_seconds,
        )
        self.sync_store = PendingSyncStore(settings.sync_state_path)
        self.syncer = RcloneSyncer(
            command=settings.rclone_command,
            config_path=settings.rclone_config_path,
            destination=settings.rclone_destination,
            timeout_seconds=settings.rclone_sync_timeout_seconds,
            store=self.sync_store,
            output_root=settings.obsidian_output_dir,
        )
        self._sync_task: asyncio.Task | None = None
        self.settings.obsidian_output_dir.mkdir(parents=True, exist_ok=True)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s", self.user)
        if self._sync_task is None:
            self._sync_task = asyncio.create_task(self._sync_loop())

    async def on_message(self, message: discord.Message) -> None:
        allowed_webhook_message = is_allowed_webhook_message(message, self.settings)
        if message.author.bot and not allowed_webhook_message:
            return
        if self.user and message.author.id == self.user.id:
            return
        if self.settings.discord_allowed_guild_ids and (
            message.guild is None or message.guild.id not in self.settings.discord_allowed_guild_ids
        ):
            return
        if self.settings.discord_allowed_channel_ids and message.channel.id not in self.settings.discord_allowed_channel_ids:
            return
        if (
            not allowed_webhook_message
            and self.settings.discord_allowed_user_ids
            and message.author.id not in self.settings.discord_allowed_user_ids
        ):
            return
        if self.store.has(message.id):
            return

        payload = build_message_payload(message)
        if payload is None:
            return

        logger.info("Processing Discord message %s", payload.message_id)
        written_files: list[str] = []
        sync_all_succeeded = True
        try:
            async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as http_client:
                if payload.urls:
                    for url in payload.urls:
                        pipeline = resolve_link_pipeline(url)
                        if pipeline is not None:
                            source = await pipeline.fetch_source_context(http_client, url, payload.note_text)
                            file_path, sync_succeeded = await self._generate_and_write_pipeline(
                                pipeline,
                                source,
                                payload,
                            )
                        else:
                            source = await fetch_source_context(http_client, url, payload.note_text)
                            file_path, sync_succeeded = await self._generate_and_write(source, payload)
                        written_files.append(str(file_path))
                        sync_all_succeeded = sync_all_succeeded and sync_succeeded
                else:
                    source = SourceContext(
                        kind="text",
                        source_url=None,
                        fetched_title=None,
                        site_name=None,
                        description=None,
                        extracted_text=payload.note_text,
                        note_text=payload.note_text,
                    )
                    file_path, sync_succeeded = await self._generate_and_write(source, payload)
                    written_files.append(str(file_path))
                    sync_all_succeeded = sync_all_succeeded and sync_succeeded
        except Exception:  # noqa: BLE001
            logger.exception("Failed to process Discord message %s", payload.message_id)
            await self._safe_react(message, "❌")
            return

        self.store.mark(payload.message_id, written_files)
        await self._safe_react(message, "✅" if sync_all_succeeded else "🕒")
        logger.info(
            "Wrote %s note(s) for message %s; sync_all_succeeded=%s",
            len(written_files),
            payload.message_id,
            sync_all_succeeded,
        )

    async def _generate_and_write(self, source: SourceContext, payload) -> tuple[Path, bool]:
        draft = await self.gemini.generate_note(source)
        note_text = render_note(
            draft=draft,
            source=source,
            message=payload,
            static_tags=self.settings.static_tags,
        )
        path = build_note_path(self.settings.obsidian_output_dir, payload.created_at, draft.title)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(note_text, encoding="utf-8")
        sync_succeeded = await self.syncer.enqueue_and_sync(path, payload.message_id, source.source_url)
        return path, sync_succeeded

    async def _generate_and_write_pipeline(self, pipeline, source: SourceContext, payload) -> tuple[Path, bool]:
        draft = await pipeline.build_note_draft(self.gemini, source)
        note_text = pipeline.render_note(draft, source, payload)
        path = pipeline.build_note_path(self.settings.obsidian_output_dir, source)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(note_text, encoding="utf-8")
        sync_succeeded = await self.syncer.enqueue_and_sync(path, payload.message_id, source.source_url)
        return path, sync_succeeded

    async def _safe_react(self, message: discord.Message, emoji: str) -> None:
        try:
            await message.add_reaction(emoji)
        except Exception:  # noqa: BLE001
            logger.debug("Could not add reaction %s to message %s", emoji, message.id)

    async def _sync_loop(self) -> None:
        try:
            while not self.is_closed():
                synced, pending = await self.syncer.sync_all_pending()
                if synced or pending:
                    logger.info("Background sync pass completed: synced=%s pending=%s", synced, pending)
                await asyncio.sleep(self.settings.rclone_sync_interval_seconds)
        except asyncio.CancelledError:
            raise

    async def close(self) -> None:
        if self._sync_task is not None:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None
        await super().close()


async def run() -> None:
    settings = load_settings()
    client = DiscordObsidianClient(settings)
    async with client:
        await client.start(settings.discord_bot_token)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
