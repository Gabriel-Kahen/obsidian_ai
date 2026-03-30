from obsidian_ai.parsing import extract_urls, normalize_tags, slugify, strip_urls


def test_extract_urls_and_strip_text() -> None:
    text = "save this https://example.com/article and this too https://example.org/test"
    assert extract_urls(text) == ["https://example.com/article", "https://example.org/test"]
    assert strip_urls(text) == "save this and this too"


def test_slugify_and_tag_normalization() -> None:
    assert slugify("Hello, World!") == "hello-world"
    assert normalize_tags(["AI Notes", "AI Notes", "obsidian/tools"]) == ["ai-notes", "obsidian-tools"]
