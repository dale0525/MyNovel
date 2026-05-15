from http import HTTPStatus
from pathlib import Path

from sqlmodel import Session

from mynovel.api_routes import dispatch_api_get, dispatch_api_post
from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import Book, BookStatus, Canon, Chapter, ChapterStatus
from mynovel.update import UpdateManifest
from mynovel.update_server import handle_check_update, handle_stage_update


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
        "/api/books/999/quality/snapshots",
        {},
        tmp_path / "dev.sqlite",
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "quality_action_failed"


def test_nested_quality_action_paths_match_react_api_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "dev.sqlite"

    style_response = dispatch_api_post(
        "/api/books/999/quality/style-assets",
        {"name": "节奏", "referenceText": "短句推进。"},
        db_path,
    )
    deconstruction_response = dispatch_api_post(
        "/api/books/999/quality/deconstruct-reference",
        {"sourceTitle": "参考章节", "referenceText": "莉拉离开村庄。"},
        db_path,
    )

    assert style_response.status == HTTPStatus.BAD_REQUEST
    assert style_response.body["error"]["code"] == "quality_action_failed"
    assert deconstruction_response.status == HTTPStatus.BAD_REQUEST
    assert deconstruction_response.body["error"]["code"] == "quality_action_failed"


def test_updates_metadata_route_returns_json(tmp_path: Path) -> None:
    response = dispatch_api_get("/api/updates", "", tmp_path / "dev.sqlite")

    assert response.status == HTTPStatus.OK
    assert response.body["currentVersion"]


def test_update_check_returns_json_instead_of_html(tmp_path: Path, monkeypatch) -> None:
    from mynovel import update_security

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

    monkeypatch.setattr(update_security, "fetch_update_manifest", fetch_manifest, raising=False)
    monkeypatch.setattr(update_security, "_allowed_update_hosts", lambda: {"example.test"})
    monkeypatch.setattr(
        update_security,
        "_resolve_update_host_addresses",
        lambda host: ["93.184.216.34"],
    )

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


def test_update_check_rejects_private_or_non_https_urls(tmp_path: Path) -> None:
    file_response = dispatch_api_post(
        "/api/updates/check",
        {"manifestUrl": "file:///etc/passwd"},
        tmp_path / "dev.sqlite",
    )
    loopback_response = dispatch_api_post(
        "/api/updates/check",
        {"manifestUrl": "http://127.0.0.1:9000/update.json"},
        tmp_path / "dev.sqlite",
    )

    assert file_response.status == HTTPStatus.BAD_REQUEST
    assert file_response.body["error"]["code"] == "update_action_failed"
    assert "https" in file_response.body["error"]["message"]
    assert loopback_response.status == HTTPStatus.BAD_REQUEST
    assert loopback_response.body["error"]["code"] == "update_action_failed"


def test_update_check_rejects_hostnames_that_resolve_to_private_ips(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from mynovel import update_security

    def fetch_manifest(_manifest_url: str) -> UpdateManifest:
        return UpdateManifest(
            channel="stable",
            version="0.2.0",
            url="https://downloads.example.test/MyNovel.dmg",
            sha256="abc123",
        )

    monkeypatch.setattr(update_security, "fetch_update_manifest", fetch_manifest, raising=False)
    monkeypatch.setattr(
        update_security,
        "_allowed_update_hosts",
        lambda: {"updates.example.test", "downloads.example.test"},
    )
    monkeypatch.setattr(
        update_security,
        "_resolve_update_host_addresses",
        lambda host: ["10.0.0.5"] if host == "updates.example.test" else ["93.184.216.34"],
    )

    response = dispatch_api_post(
        "/api/updates/check",
        {"manifestUrl": "https://updates.example.test/update.json"},
        tmp_path / "dev.sqlite",
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "update_action_failed"
    assert "private" in response.body["error"]["message"]


def test_update_check_rejects_hosts_outside_update_allowlist(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from mynovel import update_security

    def fetch_manifest(_manifest_url: str) -> UpdateManifest:
        return UpdateManifest(
            channel="stable",
            version="0.2.0",
            url="https://downloads.example.test/MyNovel.dmg",
            sha256="abc123",
        )

    monkeypatch.setattr(update_security, "fetch_update_manifest", fetch_manifest, raising=False)
    monkeypatch.setattr(
        update_security,
        "_allowed_update_hosts",
        lambda: {"updates.example.test"},
    )
    monkeypatch.setattr(
        update_security,
        "_resolve_update_host_addresses",
        lambda _host: ["93.184.216.34"],
    )

    response = dispatch_api_post(
        "/api/updates/check",
        {"manifestUrl": "https://attacker.example.test/update.json"},
        tmp_path / "dev.sqlite",
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "update_action_failed"
    assert "not an allowed update host" in response.body["error"]["message"]


def test_update_check_rejects_unsafe_artifact_url(tmp_path: Path, monkeypatch) -> None:
    from mynovel import update_security

    def fetch_manifest(_manifest_url: str) -> UpdateManifest:
        return UpdateManifest(
            channel="stable",
            version="0.2.0",
            url="http://127.0.0.1:9000/MyNovel.dmg",
            sha256="abc123",
        )

    monkeypatch.setattr(update_security, "fetch_update_manifest", fetch_manifest, raising=False)
    monkeypatch.setattr(update_security, "_allowed_update_hosts", lambda: {"example.test"})
    monkeypatch.setattr(
        update_security,
        "_resolve_update_host_addresses",
        lambda host: ["93.184.216.34"],
    )

    response = dispatch_api_post(
        "/api/updates/check",
        {"manifestUrl": "https://example.test/update.json"},
        tmp_path / "dev.sqlite",
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert response.body["error"]["code"] == "update_action_failed"


def test_legacy_update_forms_reuse_safe_url_validation(tmp_path: Path, monkeypatch) -> None:
    from mynovel import update_security

    def fetch_manifest(_manifest_url: str) -> UpdateManifest:
        return UpdateManifest(
            channel="stable",
            version="0.0.1",
            url="https://downloads.example.test/MyNovel.dmg",
            sha256="abc123",
        )

    monkeypatch.setattr(update_security, "fetch_update_manifest", fetch_manifest, raising=False)
    monkeypatch.setattr(
        update_security,
        "_allowed_update_hosts",
        lambda: {"updates.example.test", "downloads.example.test"},
    )
    monkeypatch.setattr(
        update_security,
        "_resolve_update_host_addresses",
        lambda host: ["10.0.0.5"] if host == "updates.example.test" else ["93.184.216.34"],
    )

    check_response = handle_check_update(
        {"manifest_url": "https://updates.example.test/update.json"}
    )
    stage_response = handle_stage_update(
        {"manifest_url": "https://updates.example.test/update.json"},
        tmp_path / "dev.sqlite",
    )

    assert check_response.status == HTTPStatus.BAD_REQUEST
    assert stage_response.status == HTTPStatus.BAD_REQUEST
    assert "private" in check_response.body
    assert "private" in stage_response.body


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
