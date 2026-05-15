from http import HTTPStatus
from pathlib import Path

from mynovel.static_server import resolve_spa_response


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


def test_path_traversal_is_not_served(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    assert resolve_spa_response("/assets/../secret.txt", dist).status == HTTPStatus.NOT_FOUND
