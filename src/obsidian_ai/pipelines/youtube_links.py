from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import httpx

from obsidian_ai.models import MessagePayload, NoteDraft, SourceContext
from obsidian_ai.parsing import normalize_tags, slugify

USER_AGENT = "obsidian-ai-discord-ingest/0.1 (+https://local.pi)"
MAX_FILENAME_SLUG_LENGTH = 96


def _yaml_escape(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _bounded_slug(value: str, fallback: str = "youtube") -> str:
    slug = slugify(value, fallback=fallback)
    bounded = slug[:MAX_FILENAME_SLUG_LENGTH].rstrip("-")
    return bounded or fallback


def _extract_meta(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _channel_tag(channel_name: str) -> str:
    tags = normalize_tags([channel_name])
    return tags[0] if tags else "youtube-channel"


def matches_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host in {
        "youtube.com",
        "m.youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
    }


async def fetch_source_context(
    client: httpx.AsyncClient,
    url: str,
    note_text: str,
) -> SourceContext:
    title = None
    channel = None
    extracted_text = ""

    try:
        response = await client.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
        title = str(payload.get("title", "")).strip() or None
        channel = str(payload.get("author_name", "")).strip() or None
    except Exception:
        pass

    if title is None or channel is None:
        try:
            response = await client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            title = title or _extract_meta(soup, "og:title", "twitter:title")
            channel = channel or _extract_meta(soup, "author", "og:video:tag")
        except Exception as exc:  # noqa: BLE001
            extracted_text = f"Failed to fetch YouTube metadata: {exc}"

    extracted_lines = ["Source type: YouTube link"]
    if title:
        extracted_lines.append(f"Video title: {title}")
    if channel:
        extracted_lines.append(f"Channel: {channel}")
    if note_text:
        extracted_lines.append(f"User note: {note_text}")
    if extracted_text:
        extracted_lines.append(extracted_text)

    return SourceContext(
        kind="youtube_link",
        source_url=url,
        fetched_title=title or "YouTube link",
        site_name=channel or "YouTube",
        description=None,
        extracted_text="\n".join(extracted_lines),
        note_text=note_text,
    )


async def build_note_draft(gemini, source: SourceContext) -> NoteDraft:
    generated_tags = await gemini.generate_tags(source, max_tags=1)
    title = f"{source.fetched_title or 'YouTube link'} - {source.site_name or 'YouTube'}"
    return NoteDraft(
        title=title,
        tags=generated_tags,
        summary="",
        body_markdown=source.note_text.strip(),
    )


def build_note_path(output_dir: Path, source: SourceContext) -> Path:
    title = source.fetched_title or "youtube-link"
    channel = source.site_name or "youtube"
    filename = f"{_bounded_slug(f'{title} - {channel}')}.md"
    return _unique_path(output_dir / "youtube" / filename)


def render_note(draft: NoteDraft, source: SourceContext, message: MessagePayload) -> str:
    channel_tag = _channel_tag(source.site_name or "youtube")
    generated_tags = [] if message.user_tags else draft.tags
    tags = normalize_tags([channel_tag, *generated_tags, *message.user_tags])
    frontmatter = [
        "---",
        f"link: {_yaml_escape(source.source_url or '')}",
        f"channel: {_yaml_escape(f'#{channel_tag}')}",
        f"title: {_yaml_escape(source.fetched_title or 'YouTube link')}",
        f"saved: {_yaml_escape(message.created_at.isoformat())}",
        "tags:",
    ]
    for tag in tags:
        frontmatter.append(f"  - {tag}")
    frontmatter.append("---")

    sections = ["\n".join(frontmatter)]
    if source.note_text.strip():
        sections.append(source.note_text.strip())
    return "\n\n".join(sections) + "\n"
