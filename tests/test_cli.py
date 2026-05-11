from typer.testing import CliRunner
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.cli import app
from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.workflows.open_book import create_draft_book_from_blueprint


def test_init_creates_database(tmp_path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    runner = CliRunner()

    result = runner.invoke(app, ["init", "--db", str(db_path)])

    assert result.exit_code == 0
    assert f"Initialized {db_path}" in result.output
    assert db_path.exists()


def test_run_chapter_and_audit_chapter_cli_commands(tmp_path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    _seed_book(db_path)
    runner = CliRunner()

    run_result = runner.invoke(app, ["run-chapter", "1", "--db", str(db_path)])
    audit_result = runner.invoke(app, ["audit-chapter", "1", "--db", str(db_path)])

    assert run_result.exit_code == 0
    assert "Chapter #1 is waiting for review" in run_result.output
    assert audit_result.exit_code == 0
    assert "Risk:" in audit_result.output
    assert "结尾钩子" in audit_result.output


def test_restore_book_cli_command_resets_unaccepted_chapters(tmp_path) -> None:
    db_path = tmp_path / "mynovel.sqlite"
    _seed_book(db_path)
    runner = CliRunner()
    runner.invoke(app, ["run-chapter", "1", "--db", str(db_path)])

    result = runner.invoke(app, ["restore-book", "1", "--db", str(db_path)])

    assert result.exit_code == 0
    assert "Restored book #1 to chapter 0" in result.output


def _seed_book(db_path) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        create_draft_book_from_blueprint(session, _blueprint(), selected_title="幽谷回声")


def _blueprint() -> OpenBookBlueprint:
    return OpenBookBlueprint(
        id=1,
        idea="失忆少女在幽谷中寻找被抹去的王朝真相",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content={
            "title_options": ["幽谷回声"],
            "genre": "奇幻连载",
            "audience": "喜欢成长冒险的连载读者",
            "selling_points": ["每章揭开一条旧王朝线索"],
            "protagonist": {"name": "莉拉", "hook": "失忆但能读懂古代符号"},
            "world": {"premise": "幽谷里散落着被抹去王朝的遗迹"},
            "central_conflict": "莉拉必须确认自己与旧王朝覆灭之间的关系。",
            "reader_promises": ["持续发现遗迹"],
            "chapter_directions": [{"title": "离开的召唤", "goal": "发现第一枚符号"}],
        },
        raw_response="{}",
    )
