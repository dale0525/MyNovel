from typer.testing import CliRunner

from mynovel.cli import app


def test_init_creates_database(tmp_path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    runner = CliRunner()

    result = runner.invoke(app, ["init", "--db", str(db_path)])

    assert result.exit_code == 0
    assert f"Initialized {db_path}" in result.output
    assert db_path.exists()
