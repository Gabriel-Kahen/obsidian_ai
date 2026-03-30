from obsidian_ai.sync import build_remote_path, build_staging_remote_path


def test_build_remote_path_trims_trailing_slash() -> None:
    assert build_remote_path("icloud:Obsidian/Inbox/", "note.md") == "icloud:Obsidian/Inbox/note.md"


def test_build_remote_path_requires_destination() -> None:
    try:
        build_remote_path("", "note.md")
    except ValueError as exc:
        assert "cannot be empty" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty destination")


def test_build_staging_remote_path_uses_remote_root() -> None:
    assert (
        build_staging_remote_path("icloud:Obsidian/gabenotes", "note.md")
        == "icloud:.__obsidian_ai_staging__/note.md"
    )


def test_build_staging_remote_path_requires_remote_name_and_path() -> None:
    try:
        build_staging_remote_path("icloud", "note.md")
    except ValueError as exc:
        assert "remote name" in str(exc) or "remote path" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid destination")
