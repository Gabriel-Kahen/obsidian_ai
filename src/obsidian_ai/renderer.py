from __future__ import annotations

from datetime import datetime
from pathlib import Path

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


def _bounded_slug(title: str, fallback: str = "note") -> str:
    slug = slugify(title, fallback=fallback)
    bounded = slug[:MAX_FILENAME_SLUG_LENGTH].rstrip("-")
    return bounded or fallback


def build_note_path(output_dir: Path, created_at: datetime, title: str) -> Path:
    slug = _bounded_slug(title)
    filename = f"{created_at.strftime('%Y%m%d-%H%M%S')}-{slug}.md"
    return _unique_path(output_dir / filename)


def build_title_based_note_path(output_dir: Path, title: str) -> Path:
    slug = _bounded_slug(title)
    filename = f"{slug}.md"
    return _unique_path(output_dir / filename)


def render_note(
    draft: NoteDraft,
    source: SourceContext,
    message: MessagePayload,
    static_tags: list[str],
) -> str:
    created_value = message.created_at.isoformat()
    x_tags = []
    if source.kind == "x_post":
        x_tags.append("x")
        if source.x_author_handle:
            x_tags.append(source.x_author_handle)
    all_tags = normalize_tags([*x_tags, *draft.tags] if source.kind == "x_post" else [*static_tags, *draft.tags])

    if source.kind == "x_post":
        frontmatter = [
            "---",
            f"link: {_yaml_escape(source.source_url or '')}",
            f"username: {_yaml_escape(source.x_author_handle or '')}",
            f"tweeted: {_yaml_escape(source.x_posted_at or 'Unknown')}",
            f"saved: {_yaml_escape(created_value)}",
            "tags:",
        ]
        for tag in all_tags:
            frontmatter.append(f"  - {tag}")
        frontmatter.append("---")

        sections = [
            "\n".join(frontmatter),
            f"# {draft.title}",
        ]
        if draft.body_markdown.strip():
            sections.append(draft.body_markdown.strip())
        return "\n\n".join(section.strip() for section in sections if section.strip()) + "\n"

    frontmatter = [
        "---",
        f"title: {_yaml_escape(draft.title)}",
        f"created: {_yaml_escape(created_value)}",
        f"discord_message_id: {_yaml_escape(str(message.message_id))}",
        f"discord_channel_id: {_yaml_escape(str(message.channel_id))}",
        f"discord_author: {_yaml_escape(message.author_name)}",
    ]

    if message.guild_id is not None:
        frontmatter.append(f"discord_guild_id: {_yaml_escape(str(message.guild_id))}")
    if source.source_url:
        frontmatter.append(f"source_url: {_yaml_escape(source.source_url)}")

    frontmatter.append("tags:")
    for tag in all_tags:
        frontmatter.append(f"  - {tag}")
    frontmatter.append("---")

    info_block = []
    if source.source_url:
        info_block.append(f"Source: [{source.source_url}]({source.source_url})")
    if source.fetched_title:
        info_block.append(f"Fetched title: {source.fetched_title}")
    if source.site_name:
        info_block.append(f"Site: {source.site_name}")
    if source.note_text:
        info_block.append(f"Discord note: {source.note_text}")

    sections = ["\n".join(frontmatter), f"# {draft.title}"]
    if draft.summary:
        sections.append(draft.summary)
    if info_block:
        sections.append("\n".join([f"> {line}" for line in info_block]))
    sections.append(draft.body_markdown.strip())
    return "\n\n".join(section.strip() for section in sections if section.strip()) + "\n"
