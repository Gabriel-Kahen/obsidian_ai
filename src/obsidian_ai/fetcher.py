from __future__ import annotations

from bs4 import BeautifulSoup
import httpx
import trafilatura

from obsidian_ai.models import SourceContext

USER_AGENT = "obsidian-ai-discord-ingest/0.1 (+https://local.pi)"


def _truncate(value: str, limit: int) -> str:
    return value[:limit].strip()


def _extract_meta(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


async def fetch_source_context(
    client: httpx.AsyncClient,
    url: str,
    note_text: str,
) -> SourceContext:
    fetched_title = None
    site_name = None
    description = None
    extracted_text = ""

    try:
        response = await client.get(
            url,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" in content_type or content_type.startswith("text/") or not content_type:
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            fetched_title = (
                _extract_meta(soup, "og:title", "twitter:title")
                or (soup.title.string.strip() if soup.title and soup.title.string else None)
            )
            site_name = _extract_meta(soup, "og:site_name")
            description = _extract_meta(soup, "description", "og:description", "twitter:description")
            extracted_text = trafilatura.extract(html, output_format="txt", include_comments=False) or ""
        else:
            extracted_text = f"Unsupported content type for deep extraction: {content_type}"
    except Exception as exc:  # noqa: BLE001
        extracted_text = f"Failed to fetch source content: {exc}"

    return SourceContext(
        kind="url",
        source_url=url,
        fetched_title=fetched_title,
        site_name=site_name,
        description=description,
        extracted_text=_truncate(extracted_text, 8000),
        note_text=note_text,
    )
