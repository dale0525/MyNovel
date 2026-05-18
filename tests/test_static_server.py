from http import HTTPStatus
from pathlib import Path

from mynovel.dev_server import _classify_get_path
from mynovel.frontend_assets import frontend_dist_path_from_module
from mynovel.static_server import resolve_spa_response


def test_frontend_dist_path_prefers_package_sibling_dist(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "mynovel" / "frontend_assets.py"
    package_dist = module_file.parent / "frontend" / "dist"
    repo_dist = tmp_path / "frontend" / "dist"
    package_dist.mkdir(parents=True)
    repo_dist.mkdir(parents=True)

    assert frontend_dist_path_from_module(module_file) == package_dist


def test_frontend_dist_path_falls_back_to_source_tree_dist(tmp_path: Path) -> None:
    module_file = tmp_path / "src" / "mynovel" / "frontend_assets.py"

    assert frontend_dist_path_from_module(module_file) == tmp_path / "frontend" / "dist"


def test_get_route_classification_preserves_downloads_and_static_fallback() -> None:
    assert _classify_get_path("/api/books") == "api"
    assert _classify_get_path("/api/books/42/export.md") == "api"
    assert _classify_get_path("/api/books/42/export.json") == "api"
    assert _classify_get_path("/api/chapters/9/export.txt") == "api"
    assert _classify_get_path("/book/42/export.md") == "static"
    assert _classify_get_path("/chapter/9/export") == "static"
    assert _classify_get_path("/assets/app.js") == "static"
    assert _classify_get_path("/books/1") == "static"


def test_app_route_serves_index(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
    response = resolve_spa_response("/books/1", dist)
    assert response.status == HTTPStatus.OK
    assert response.content_type == "text/html; charset=utf-8"


def test_asset_route_serves_asset(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    response = resolve_spa_response("/assets/app.js", dist)
    assert response.status == HTTPStatus.OK
    assert response.content_type == "text/javascript"


def test_javascript_asset_type_is_stable_across_platform_mimetypes(
    tmp_path: Path, monkeypatch
) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setattr(
        "mynovel.static_server.mimetypes.guess_type",
        lambda _: ("application/javascript", None),
    )

    response = resolve_spa_response("/assets/app.js", dist)

    assert response.status == HTTPStatus.OK
    assert response.content_type == "text/javascript"


def test_path_traversal_is_not_served(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    assert resolve_spa_response("/assets/../secret.txt", dist).status == HTTPStatus.NOT_FOUND


def test_encoded_path_traversal_is_not_served(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    assert resolve_spa_response("/assets/%2e%2e/secret.txt", dist).status == HTTPStatus.NOT_FOUND


def test_missing_index_reports_frontend_not_built(tmp_path: Path) -> None:
    response = resolve_spa_response("/books/1", tmp_path / "dist")

    assert response.status == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.content_type == "text/plain; charset=utf-8"
    assert b"pixi run preview" in response.body


def test_packaged_provider_setup_does_not_require_rerank_model() -> None:
    dist = frontend_dist_path_from_module(Path("src/mynovel/frontend_assets.py"))
    bundled_text = "\n".join(
        asset.read_text(encoding="utf-8") for asset in (dist / "assets").glob("*.js")
    )

    assert "Rerank model name" not in bundled_text


def test_packaged_frontend_includes_ai_waiting_animation() -> None:
    dist = frontend_dist_path_from_module(Path("src/mynovel/frontend_assets.py"))
    bundled_js = "\n".join(
        asset.read_text(encoding="utf-8") for asset in (dist / "assets").glob("*.js")
    )
    bundled_css = "\n".join(
        asset.read_text(encoding="utf-8") for asset in (dist / "assets").glob("*.css")
    )

    assert "ai-waiting" in bundled_css
    assert "AiWaitingIndicator" in bundled_js or "ai-waiting-indicator" in bundled_js
    assert "蓝图生成中" in bundled_js
