from __future__ import annotations

import re
import unicodedata

from obsidian_ai.models import MessagePayload

URL_PATTERN = re.compile(r"https?://[^\s<>]+")


def extract_urls(text: str) -> list[str]:
    urls = []
    for match in URL_PATTERN.findall(text):
        cleaned = match.rstrip(".,!?)]}>")
        urls.append(cleaned)
    return urls


def strip_urls(text: str) -> str:
    without_urls = URL_PATTERN.sub(" ", text)
    return " ".join(without_urls.split())


def slugify(value: str, fallback: str = "note") -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    lowered = normalized.lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return lowered or fallback


def normalize_tags(tags: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for tag in tags:
        cleaned = slugify(tag.replace("/", "-"), fallback="")
        if cleaned and cleaned not in seen:
            normalized.append(cleaned)
            seen.add(cleaned)
    return normalized


def build_message_payload(message) -> MessagePayload | None:
    attachment_urls = [attachment.url for attachment in message.attachments]
    raw_content = message.content or ""
    urls = extract_urls(raw_content)
    urls.extend(url for url in attachment_urls if url not in urls)

    note_text = strip_urls(raw_content)
    if not urls and not note_text:
        return None

    return MessagePayload(
        message_id=message.id,
        channel_id=message.channel.id,
        guild_id=message.guild.id if message.guild else None,
        author_id=message.author.id,
        author_name=str(message.author),
        created_at=message.created_at,
        raw_content=raw_content,
        note_text=note_text,
        urls=urls,
    )
