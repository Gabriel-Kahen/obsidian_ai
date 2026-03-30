from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from obsidian_ai.models import PendingSync


class ProcessedMessageStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[str, list[str]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def has(self, message_id: int) -> bool:
        return str(message_id) in self._data

    def mark(self, message_id: int, files: list[str]) -> None:
        self._data[str(message_id)] = files
        temp_path = self._path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(self._path)


class PendingSyncStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[str, PendingSync]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

        items: dict[str, PendingSync] = {}
        for local_path, payload in raw.items():
            if isinstance(payload, dict):
                items[local_path] = PendingSync(**payload)
        return items

    def _save(self) -> None:
        serializable = {local_path: asdict(item) for local_path, item in self._data.items()}
        temp_path = self._path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(serializable, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(self._path)

    def upsert(self, item: PendingSync) -> None:
        self._data[item.local_path] = item
        self._save()

    def get(self, local_path: str) -> PendingSync | None:
        return self._data.get(local_path)

    def remove(self, local_path: str) -> None:
        if local_path in self._data:
            del self._data[local_path]
            self._save()

    def list_pending(self) -> list[PendingSync]:
        return list(self._data.values())

    def update_attempt(
        self,
        local_path: str,
        attempt_count: int,
        last_attempted_at: str,
        last_error: str,
    ) -> None:
        item = self._data.get(local_path)
        if item is None:
            return
        self._data[local_path] = PendingSync(
            local_path=item.local_path,
            remote_path=item.remote_path,
            message_id=item.message_id,
            source_url=item.source_url,
            enqueued_at=item.enqueued_at,
            attempt_count=attempt_count,
            last_attempted_at=last_attempted_at,
            last_error=last_error,
        )
        self._save()
