from http import HTTPStatus
from pathlib import Path

from mynovel.api_routes import dispatch_api_get


def test_unknown_api_route_returns_json_error(tmp_path: Path) -> None:
    response = dispatch_api_get("/api/missing", "", tmp_path / "dev.sqlite")
    assert response.status == HTTPStatus.NOT_FOUND
    assert response.body["error"]["code"] == "not_found"


def test_bootstrap_requires_setup_without_provider(tmp_path: Path) -> None:
    response = dispatch_api_get("/api/app/bootstrap", "", tmp_path / "dev.sqlite")
    assert response.body["providerConfigured"] is False
    assert response.body["initialRoute"] == "/setup"
