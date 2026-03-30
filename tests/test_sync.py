from obsidian_ai.sync import build_remote_path


def test_build_remote_path_trims_trailing_slash() -> None:
    assert build_remote_path("icloud:Obsidian/Inbox/", "note.md") == "icloud:Obsidian/Inbox/note.md"


def test_build_remote_path_requires_destination() -> None:
    try:
        build_remote_path("", "note.md")
    except ValueError as exc:
        assert "cannot be empty" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty destination")
