from __future__ import annotations

from urllib.parse import urlparse

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


def _is_x_post(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in {"x.com", "twitter.com", "mobile.twitter.com"}:
        return False
    path_parts = [part for part in parsed.path.split("/") if part]
    return len(path_parts) >= 3 and path_parts[1] == "status"


def _clean_x_description(description: str) -> str:
    cleaned = description.strip()
    if cleaned.startswith('"') and '" / X' in cleaned:
        return cleaned.split('" / X', 1)[0].strip('"')
    if cleaned.endswith(" / X"):
        return cleaned[: -len(" / X")].strip()
    return cleaned


def _extract_x_post_text(soup: BeautifulSoup, url: str) -> tuple[str | None, str | None]:
    description = (
        _extract_meta(soup, "twitter:description", "og:description", "description")
        or ""
    ).strip()
    post_text = _clean_x_description(description) if description else None

    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    author_handle = path_parts[0] if path_parts else None
    return post_text, author_handle


def _build_x_extracted_text(post_text: str | None, author_handle: str | None, note_text: str) -> str:
    lines = ["Source type: X post"]
    if author_handle:
        lines.append(f"Author handle: @{author_handle}")
    if post_text:
        lines.append(f"Post text: {post_text}")
    else:
        lines.append("Post text: unavailable")
    if note_text:
        lines.append(f"User note: {note_text}")
    return "\n".join(lines)


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
            if _is_x_post(url):
                post_text, author_handle = _extract_x_post_text(soup, url)
                extracted_text = _build_x_extracted_text(post_text, author_handle, note_text)
            else:
                extracted_text = trafilatura.extract(html, output_format="txt", include_comments=False) or ""
        else:
            extracted_text = f"Unsupported content type for deep extraction: {content_type}"
    except Exception as exc:  # noqa: BLE001
        extracted_text = f"Failed to fetch source content: {exc}"

    return SourceContext(
        kind="x_post" if _is_x_post(url) else "url",
        source_url=url,
        fetched_title=fetched_title,
        site_name=site_name,
        description=description,
        extracted_text=_truncate(extracted_text, 8000),
        note_text=note_text,
    )
