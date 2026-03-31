from __future__ import annotations

import json

import httpx

from obsidian_ai.models import NoteDraft, SourceContext
from obsidian_ai.parsing import normalize_tags


class GeminiError(RuntimeError):
    """Raised when Gemini returns an invalid response."""


class GeminiClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def generate_note(self, source: SourceContext) -> NoteDraft:
        prompt = self._build_prompt(source)
        payload = await self._call_gemini(prompt)

        title = str(payload.get("title", "")).strip() or "Untitled Note"
        summary = str(payload.get("summary", "")).strip()
        body_markdown = str(payload.get("body_markdown", "")).strip()
        tags = normalize_tags([str(tag) for tag in payload.get("tags", [])])

        if not body_markdown:
            raise GeminiError("Gemini returned an empty body_markdown field")

        return NoteDraft(
            title=title,
            tags=tags,
            summary=summary,
            body_markdown=body_markdown,
        )

    async def generate_tags(self, source: SourceContext, max_tags: int = 2) -> list[str]:
        payload = await self._call_gemini(self._build_tag_prompt(source))
        return normalize_tags([str(tag) for tag in payload.get("tags", [])])[:max_tags]

    async def _call_gemini(self, prompt: str) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url,
                params={"key": self._api_key},
                json={
                    "systemInstruction": {
                        "parts": [
                            {
                                "text": (
                                    "You convert captured links and notes into clean Obsidian notes. "
                                    "Be honest about uncertainty. Do not invent facts missing from the provided source."
                                )
                            }
                        ]
                    },
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.3,
                    },
                },
            )
            response.raise_for_status()

        text = self._extract_text(response.json())
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiError(f"Gemini did not return valid JSON: {text}") from exc

    def _extract_text(self, payload: dict) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            raise GeminiError(f"Gemini returned no candidates: {payload}")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise GeminiError(f"Gemini returned no text part: {payload}")
        return parts[0]["text"]

    def _build_prompt(self, source: SourceContext) -> str:
        source_label = {
            "text": "text note",
            "x_post": "captured X post",
        }.get(source.kind, "captured web link")
        return f"""
Create one Obsidian-ready note from this {source_label}.

Return JSON only with this exact shape:
{{
  "title": "string",
  "tags": ["string"],
  "summary": "1-3 sentence summary",
  "body_markdown": "markdown without YAML frontmatter and without a top-level H1 title"
}}

Rules:
- Be concise and factual.
- If source material is weak or incomplete, say that plainly.
- Do not claim to have visited content that is not included below.
- Prefer durable tags, not overly specific one-off tags.
- The markdown body should be useful in Obsidian and can include sections like "Key Points", "Takeaway", or "Open Questions".
- If this is an X post, include the post text explicitly in the markdown body and preserve the user's own note separately.
- If this is an X post, include tags that make the source obvious, such as x-post or tweet, plus relevant topical tags.

Source URL: {source.source_url or "none"}
Source kind: {source.kind}
Fetched title: {source.fetched_title or "none"}
Site name: {source.site_name or "none"}
Description: {source.description or "none"}
User note: {source.note_text or "none"}

Extracted source text:
{source.extracted_text or "No extracted text available."}
""".strip()

    def _build_tag_prompt(self, source: SourceContext) -> str:
        return f"""
Return JSON only with this exact shape:
{{
  "tags": ["string"]
}}

Rules:
- Generate only broad topical or organizational tags.
- Usually return exactly 1 tag.
- Return a second tag only when the source clearly spans two distinct high-level categories.
- Return at most 2 tags.
- Do not include generic source tags like x, tweet, or the author's username; those are added separately.
- Prefer category or intent tags like ai, funny, politics, design, psychology, productivity, art, or philosophy.
- Do not use literal object words, named entities, quotes, or low-level subject matter from the post as tags.
- Avoid micro-topic tags like peanut-butter, vape, idea, or evaluation unless they are genuinely the broad category.
- If the post is intended to be humorous, absurd, or a joke, include the tag "funny".
- Avoid low-signal noun tags copied directly from the tweet unless they clearly represent the broader category.
- Be concise and factual.
- Do not invent details not present in the source.

Source URL: {source.source_url or "none"}
Source kind: {source.kind}
Fetched title: {source.fetched_title or "none"}
Description: {source.description or "none"}
User note: {source.note_text or "none"}

Extracted source text:
{source.extracted_text or "No extracted text available."}
""".strip()
