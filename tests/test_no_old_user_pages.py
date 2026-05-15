from pathlib import Path


def test_dev_server_does_not_import_html_renderers() -> None:
    source = Path("src/mynovel/dev_server.py").read_text(encoding="utf-8")
    assert "render_home" not in source
    assert "render_model_setup_page" not in source
    assert "render_book_workspace" not in source
    assert "render_chapter_review" not in source


def test_no_send_html_user_route_remains() -> None:
    source = Path("src/mynovel/dev_server.py").read_text(encoding="utf-8")
    assert "_send_html(" not in source
