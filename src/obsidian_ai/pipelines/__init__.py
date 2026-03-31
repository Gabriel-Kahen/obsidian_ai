from __future__ import annotations

from typing import Protocol

from obsidian_ai.models import MessagePayload, NoteDraft, SourceContext

from . import generic_links
from . import x_posts
from . import youtube_links


class LinkPipeline(Protocol):
    def matches_url(self, url: str) -> bool: ...
    async def fetch_source_context(self, client, url: str, note_text: str) -> SourceContext: ...
    async def build_note_draft(self, gemini, source: SourceContext) -> NoteDraft: ...
    def build_note_path(self, output_dir, source: SourceContext): ...
    def render_note(self, draft: NoteDraft, source: SourceContext, message: MessagePayload) -> str: ...


REGISTERED_LINK_PIPELINES: tuple[LinkPipeline, ...] = (
    x_posts,
    youtube_links,
    generic_links,
)


def resolve_link_pipeline(url: str) -> LinkPipeline | None:
    for pipeline in REGISTERED_LINK_PIPELINES:
        if pipeline.matches_url(url):
            return pipeline
    return None
