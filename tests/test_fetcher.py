from obsidian_ai.fetcher import (
    _build_x_extracted_text,
    _clean_x_description,
    _extract_text_from_oembed_html,
    _is_x_post,
)


def test_is_x_post_detects_status_urls() -> None:
    assert _is_x_post("https://x.com/gabe/status/123")
    assert _is_x_post("https://twitter.com/gabe/status/123")
    assert not _is_x_post("https://x.com/home")


def test_clean_x_description_removes_x_suffix() -> None:
    assert _clean_x_description('"hello world" / X') == "hello world"
    assert _clean_x_description("hello world / X") == "hello world"


def test_build_x_extracted_text_preserves_post_and_note() -> None:
    extracted = _build_x_extracted_text("some post text", "gabe", "my comment")
    assert "Author handle: @gabe" in extracted
    assert "Post text: some post text" in extracted
    assert "User note: my comment" in extracted


def test_extract_text_from_oembed_html_reads_post_text_and_handle() -> None:
    oembed_html = (
        '<blockquote class="twitter-tweet"><p lang="en" dir="ltr">hello world</p>'
        '&mdash; Gabe (@gabek) <a href="https://x.com/gabek/status/1?ref_src=twsrc%5Etfw">March 1, 2026</a>'
        "</blockquote>"
    )
    post_text, author_handle, posted_at = _extract_text_from_oembed_html(oembed_html)
    assert post_text == "hello world"
    assert author_handle == "gabek"
    assert posted_at == "March 1, 2026"
