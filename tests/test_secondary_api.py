from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session

from mynovel import api_routes
from mynovel.api_routes import dispatch_api_get, dispatch_api_post
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, BookStatus, Canon, Chapter, ChapterStatus
from mynovel.update import UpdateManifest


def test_invalid_import_returns_import_failed(tmp_path: Path) -> None:
    response = dispatch_api_post(
        "/api/books/import",
        {"projectJson": "{not-json"},
        tmp_path / "dev.sqlite",
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "import_failed"


def test_unknown_quality_snapshot_book_returns_quality_action_failed(tmp_path: Path) -> None:
    response = dispatch_api_post(
        "/api/books/999/quality-snapshots",
        {},
        tmp_path / "dev.sqlite",
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "quality_action_failed"


def test_update_check_returns_json_instead_of_html(tmp_path: Path, monkeypatch) -> None:
    def fetch_manifest(manifest_url: str) -> UpdateManifest:
        assert manifest_url == "https://example.test/update.json"
        return UpdateManifest(
            channel="stable",
            version="0.2.0",
            url="https://example.test/MyNovel.dmg",
            sha256="abc123",
            notes="修复章节恢复。",
            published_at="2026-05-11T00:00:00Z",
            size_bytes=123456,
        )

    monkeypatch.setattr(api_routes, "fetch_update_manifest", fetch_manifest, raising=False)

    response = dispatch_api_post(
        "/api/updates/check",
        {"manifestUrl": "https://example.test/update.json"},
        tmp_path / "dev.sqlite",
    )

    assert response.status == HTTPStatus.OK
    assert response.content_type == "application/json; charset=utf-8"
    assert response.body["result"]["available"] is True
    assert response.body["result"]["version"] == "0.2.0"
    assert "<html" not in str(response.body).lower()


def test_book_exports_are_available_under_api_download_routes(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = Book(
            title="星港遗梦",
            genre="科幻",
            audience="成人",
            status=BookStatus.PRODUCING,
            premise="领航员追查失落星港的真相。",
        )
        session.add(book)
        session.commit()
        session.refresh(book)
        session.add(Canon(book_id=book.id or 0, version=2, content={"characters": []}))
        session.add(
            Chapter(
                book_id=book.id or 0,
                number=1,
                title="失落灯塔",
                status=ChapterStatus.ACCEPTED,
                final_text="灯塔已经点亮。",
                word_count=7,
            )
        )
        session.commit()
        book_id = book.id or 0

    markdown = dispatch_api_get(f"/api/books/{book_id}/export.md", "", db_path)
    exported_json = dispatch_api_get(f"/api/books/{book_id}/export.json", "", db_path)

    assert markdown.status == HTTPStatus.OK
    assert markdown.content_type == "text/markdown; charset=utf-8"
    assert "# 星港遗梦" in markdown.body
    assert "灯塔已经点亮。" in markdown.body
    assert exported_json.status == HTTPStatus.OK
    assert exported_json.body["book"]["title"] == "星港遗梦"
    assert exported_json.body["trusted_state"]["version"] == 2
