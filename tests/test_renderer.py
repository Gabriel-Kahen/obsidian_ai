from datetime import datetime, timezone

from obsidian_ai.models import MessagePayload, NoteDraft, SourceContext
from obsidian_ai.renderer import build_title_based_note_path, render_note


def test_render_x_post_uses_minimal_properties_and_body() -> None:
    draft = NoteDraft(
        title="my note",
        tags=["intrusive-thoughts"],
        summary="",
        body_markdown="tweet body",
    )
    source = SourceContext(
        kind="x_post",
        source_url="https://x.com/gabek/status/1",
        fetched_title="ignored",
        site_name="X",
        description="tweet body",
        extracted_text="Source type: X post",
        note_text="my note",
        x_author_handle="gabek",
        x_posted_at="March 30, 2026",
        x_post_text="tweet body",
    )
    message = MessagePayload(
        message_id=1,
        channel_id=2,
        guild_id=3,
        author_id=4,
        author_name="gabe",
        created_at=datetime(2026, 3, 30, 23, 59, 36, tzinfo=timezone.utc),
        raw_content="",
        note_text="my note",
        urls=["https://x.com/gabek/status/1"],
    )

    rendered = render_note(draft, source, message, static_tags=["inbox"])

    assert 'link: "https://x.com/gabek/status/1"' in rendered
    assert 'username: "gabek"' in rendered
    assert 'tweeted: "March 30, 2026"' in rendered
    assert 'saved: "2026-03-30T23:59:36+00:00"' in rendered
    assert "  - x" in rendered
    assert "  - gabek" in rendered
    assert "  - intrusive-thoughts" in rendered
    assert "# my note" in rendered
    assert "tweet body" in rendered
    assert "## Tags" not in rendered
    assert "## Metadata" not in rendered
    assert 'title: "' not in rendered


def test_build_title_based_note_path_uses_title_slug(tmp_path) -> None:
    path = build_title_based_note_path(tmp_path, "just thought of a peanut butter vape")
    assert path.name == "just-thought-of-a-peanut-butter-vape.md"
