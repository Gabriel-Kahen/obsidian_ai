from obsidian_ai.fetcher import _build_x_extracted_text, _clean_x_description, _is_x_post


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
