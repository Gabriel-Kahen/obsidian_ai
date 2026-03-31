from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MessagePayload:
    message_id: int
    channel_id: int
    guild_id: int | None
    author_id: int
    author_name: str
    created_at: datetime
    raw_content: str
    note_text: str
    urls: list[str]


@dataclass(frozen=True)
class SourceContext:
    kind: str
    source_url: str | None
    fetched_title: str | None
    site_name: str | None
    description: str | None
    extracted_text: str
    note_text: str
    x_author_handle: str | None = None
    x_author_name: str | None = None
    x_posted_at: str | None = None
    x_post_text: str | None = None


@dataclass(frozen=True)
class NoteDraft:
    title: str
    tags: list[str]
    summary: str
    body_markdown: str


@dataclass(frozen=True)
class PendingSync:
    local_path: str
    remote_path: str
    message_id: int
    source_url: str | None
    enqueued_at: str
    attempt_count: int = 0
    last_attempted_at: str | None = None
    last_error: str | None = None
