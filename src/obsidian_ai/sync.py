from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from obsidian_ai.models import PendingSync
from obsidian_ai.state import PendingSyncStore

logger = logging.getLogger("obsidian_ai.sync")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_remote_path(destination: str, filename: str) -> str:
    destination = destination.rstrip("/")
    if not destination:
        raise ValueError("RCLONE_DESTINATION cannot be empty")
    return f"{destination}/{filename}"


def build_staging_remote_path(destination: str, filename: str) -> str:
    remote_name, _, remote_subpath = destination.partition(":")
    if not remote_name:
        raise ValueError("RCLONE_DESTINATION must include a remote name like 'icloud:Obsidian/gabenotes'")
    if remote_subpath == "":
        raise ValueError("RCLONE_DESTINATION must include a remote path after ':'")
    return f"{remote_name}:.__obsidian_ai_staging__/{filename}"


class RcloneSyncer:
    def __init__(
        self,
        command: str,
        destination: str,
        timeout_seconds: float,
        store: PendingSyncStore,
        config_path: Path | None = None,
    ) -> None:
        self._command = command
        self._destination = destination
        self._timeout_seconds = timeout_seconds
        self._config_path = config_path
        self._store = store
        self._lock = asyncio.Lock()

    async def enqueue(self, local_path: Path, message_id: int, source_url: str | None) -> None:
        item = PendingSync(
            local_path=str(local_path),
            remote_path=build_remote_path(self._destination, local_path.name),
            message_id=message_id,
            source_url=source_url,
            enqueued_at=_utc_now_iso(),
        )
        self._store.upsert(item)

    async def enqueue_and_sync(self, local_path: Path, message_id: int, source_url: str | None) -> bool:
        await self.enqueue(local_path, message_id, source_url)
        return await self.sync_one(str(local_path))

    async def sync_one(self, local_path: str) -> bool:
        async with self._lock:
            item = self._store.get(local_path)
            if item is None:
                return True
            return await self._sync_locked(item)

    async def sync_all_pending(self) -> tuple[int, int]:
        async with self._lock:
            synced = 0
            pending = 0
            for item in self._store.list_pending():
                if await self._sync_locked(item):
                    synced += 1
                else:
                    pending += 1
            return synced, pending

    async def _sync_locked(self, item: PendingSync) -> bool:
        local_path = Path(item.local_path)
        if not local_path.exists():
            self._store.update_attempt(
                local_path=item.local_path,
                attempt_count=item.attempt_count + 1,
                last_attempted_at=_utc_now_iso(),
                last_error="Local file no longer exists",
            )
            return False

        staging_remote_path = build_staging_remote_path(self._destination, local_path.name)
        copy_result = await self._run_rclone(
            "copyto",
            str(local_path),
            staging_remote_path,
        )
        if copy_result is not None:
            self._store.update_attempt(
                local_path=item.local_path,
                attempt_count=item.attempt_count + 1,
                last_attempted_at=_utc_now_iso(),
                last_error=copy_result[:2000],
            )
            return False

        move_result = await self._run_rclone(
            "moveto",
            staging_remote_path,
            item.remote_path,
        )
        if move_result is None:
            self._store.remove(item.local_path)
            logger.info("Synced %s to %s", item.local_path, item.remote_path)
            return True

        self._store.update_attempt(
            local_path=item.local_path,
            attempt_count=item.attempt_count + 1,
            last_attempted_at=_utc_now_iso(),
            last_error=move_result[:2000],
        )
        logger.warning("Failed to sync %s: %s", item.local_path, move_result)
        return False

    async def _run_rclone(self, operation: str, source: str, target: str) -> str | None:
        command = [self._command]
        if self._config_path is not None:
            command.extend(["--config", str(self._config_path)])
        command.extend(
            [
                operation,
                "--retries",
                "1",
                "--low-level-retries",
                "1",
                source,
                target,
            ]
        )

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._timeout_seconds)
        except TimeoutError:
            process.kill()
            await process.wait()
            return f"rclone {operation} timed out after {self._timeout_seconds:.0f}s"

        if process.returncode == 0:
            return None

        error_parts = []
        if stdout:
            error_parts.append(stdout.decode("utf-8", errors="replace").strip())
        if stderr:
            error_parts.append(stderr.decode("utf-8", errors="replace").strip())
        error_text = " | ".join(part for part in error_parts if part).strip()
        return error_text or f"rclone {operation} exited with {process.returncode}"
