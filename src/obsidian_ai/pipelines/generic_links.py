from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from obsidian_ai.models import MessagePayload, NoteDraft, SourceContext
from obsidian_ai.parsing import normalize_tags, slugify

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


def _bounded_slug(value: str, fallback: str = "link") -> str:
    slug = slugify(value, fallback=fallback)
    bounded = slug[:MAX_FILENAME_SLUG_LENGTH].rstrip("-")
    return bounded or fallback


def _website_name(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    parts = [part for part in host.split(".") if part]
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in {"co", "com", "org", "net"}:
        return parts[-3]
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else "website"


def matches_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def fetch_source_context(
    client,
    url: str,
    note_text: str,
) -> SourceContext:
    del client
    website = _website_name(url)
    return SourceContext(
        kind="generic_link",
        source_url=url,
        fetched_title=note_text or website,
        site_name=website,
        description=None,
        extracted_text="",
        note_text=note_text,
    )


async def build_note_draft(gemini, source: SourceContext) -> NoteDraft:
    del gemini
    return NoteDraft(
        title=source.note_text.strip() or source.fetched_title or "link",
        tags=[],
        summary="",
        body_markdown="",
    )


def build_note_path(output_dir: Path, source: SourceContext) -> Path:
    filename = f"{_bounded_slug(source.note_text or source.fetched_title or 'link')}.md"
    return _unique_path(output_dir / filename)


def render_note(draft: NoteDraft, source: SourceContext, message: MessagePayload) -> str:
    website = normalize_tags([source.site_name or "website"])
    website_tag = f"#{website[0]}" if website else "#website"
    frontmatter = [
        "---",
        f"link: {_yaml_escape(source.source_url or '')}",
        f"website: {_yaml_escape(website_tag)}",
        f"saved: {_yaml_escape(message.created_at.isoformat())}",
        "tags:",
    ]
    for tag in message.user_tags:
        frontmatter.append(f"  - {tag}")
    frontmatter.append("---")
    return "\n".join(frontmatter) + "\n"
