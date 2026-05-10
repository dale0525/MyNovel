from pathlib import Path

from mynovel.db import create_db_and_tables, create_engine_for_path


def test_create_db_and_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    engine = create_engine_for_path(db_path)

    create_db_and_tables(engine)

    assert db_path.exists()
