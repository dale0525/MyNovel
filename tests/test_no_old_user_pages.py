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


def test_old_renderer_modules_are_removed() -> None:
    removed_modules = [
        "blueprint_views.py",
        "chapter_review_views.py",
        "dev_views.py",
        "home_views.py",
        "import_views.py",
        "model_setup_views.py",
        "open_book_views.py",
        "product_views.py",
        "provider_config_server.py",
        "quality_views.py",
        "ui_shell.py",
        "ui_status_views.py",
        "update_server.py",
        "update_views.py",
        "word_target_server.py",
        "word_target_views.py",
        "workspace_views.py",
    ]

    for module in removed_modules:
        assert not Path("src/mynovel", module).exists()
