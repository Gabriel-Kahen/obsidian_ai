from __future__ import annotations

import re
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


def _extract_text_from_oembed_html(oembed_html: str) -> tuple[str | None, str | None, str | None]:
    soup = BeautifulSoup(oembed_html, "html.parser")
    blockquote = soup.find("blockquote")
    paragraph = blockquote.find("p") if blockquote else None
    post_text = paragraph.get_text(" ", strip=True) if paragraph else None

    author_handle = None
    posted_at = None
    if blockquote:
        blockquote_text = blockquote.get_text(" ", strip=True)
        handle_match = re.search(r"\(@([A-Za-z0-9_]+)\)", blockquote_text)
        if handle_match:
            author_handle = handle_match.group(1)

        links = blockquote.find_all("a")
        if links:
            posted_at = links[-1].get_text(" ", strip=True) or None

    return post_text, author_handle, posted_at


async def _fetch_x_oembed_context(
    client: httpx.AsyncClient,
    url: str,
    note_text: str,
) -> SourceContext | None:
    endpoints = [
        "https://publish.x.com/oembed",
        "https://publish.twitter.com/oembed",
    ]

    last_error = None
    for endpoint in endpoints:
        try:
            response = await client.get(
                endpoint,
                params={
                    "url": url,
                    "omit_script": "true",
                    "dnt": "true",
                },
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            payload = response.json()
            post_text, author_handle, posted_at = _extract_text_from_oembed_html(payload.get("html", ""))
            if not post_text:
                continue

            extracted_text = _build_x_extracted_text(post_text, author_handle, note_text)
            title = payload.get("author_name") or payload.get("title")
            if not title:
                title = f"X post by @{author_handle}" if author_handle else "X post"
            return SourceContext(
                kind="x_post",
                source_url=url,
                fetched_title=str(title).strip() if title else "X post",
                site_name="X",
                description=post_text,
                extracted_text=_truncate(extracted_text, 8000),
                note_text=note_text,
                x_author_handle=author_handle,
                x_author_name=str(payload.get("author_name", "")).strip() or None,
                x_posted_at=posted_at,
                x_post_text=post_text,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    if last_error is not None:
        return SourceContext(
            kind="x_post",
            source_url=url,
            fetched_title="X post",
            site_name="X",
            description=None,
            extracted_text=_truncate(f"Failed to fetch X oEmbed content: {last_error}", 8000),
            note_text=note_text,
            x_author_handle=None,
            x_author_name=None,
            x_posted_at=None,
            x_post_text=None,
        )
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
    post_text = None
    author_handle = None

    try:
        if _is_x_post(url):
            x_context = await _fetch_x_oembed_context(client, url, note_text)
            if x_context is not None and "Failed to fetch X oEmbed content:" not in x_context.extracted_text:
                return x_context

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
            post_text = None
            author_handle = None
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
        x_author_handle=author_handle if _is_x_post(url) else None,
        x_author_name=None,
        x_posted_at=None,
        x_post_text=post_text if _is_x_post(url) else None,
    )
