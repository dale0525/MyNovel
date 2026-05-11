from pathlib import Path

import typer
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.repositories import get_chapter
from mynovel.workflows.chapter_pipeline import run_chapter_pipeline
from mynovel.workflows.open_book import create_draft_book
from mynovel.workflows.recovery import restore_to_latest_accepted_point

app = typer.Typer(no_args_is_help=True)


@app.command()
def init(db: Path = typer.Option(Path("mynovel.sqlite"), help="SQLite database path.")) -> None:
    engine = create_engine_for_path(db)
    create_db_and_tables(engine)
    typer.echo(f"Initialized {db}")


@app.command("open-book")
def open_book(
    idea: str = typer.Argument(...),
    genre: str = typer.Option("web-novel"),
    audience: str = typer.Option("web novel readers"),
    db: Path = typer.Option(Path("mynovel.sqlite")),
) -> None:
    engine = create_engine_for_path(db)
    create_db_and_tables(engine)
    with Session(engine) as session:
        book = create_draft_book(session, idea=idea, genre=genre, audience=audience)
    typer.echo(f"Created draft book #{book.id}: {book.premise}")


@app.command("run-chapter")
def run_chapter(
    chapter_id: int = typer.Argument(...),
    db: Path = typer.Option(Path("mynovel.sqlite")),
) -> None:
    engine = create_engine_for_path(db)
    create_db_and_tables(engine)
    with Session(engine) as session:
        chapter = run_chapter_pipeline(session, chapter_id)
    typer.echo(f"Chapter #{chapter.id} is waiting for review: {chapter.title}")


@app.command("audit-chapter")
def audit_chapter(
    chapter_id: int = typer.Argument(...),
    db: Path = typer.Option(Path("mynovel.sqlite")),
) -> None:
    engine = create_engine_for_path(db)
    create_db_and_tables(engine)
    with Session(engine) as session:
        chapter = get_chapter(session, chapter_id)
        if chapter is None:
            raise typer.BadParameter("Chapter does not exist.")
        if not chapter.audit_report:
            chapter = run_chapter_pipeline(session, chapter_id)

    typer.echo(f"Risk: {chapter.audit_report.get('risk_level', 'unknown')}")
    for issue in chapter.audit_report.get("issues", []):
        if isinstance(issue, dict):
            typer.echo(f"- {issue.get('title', '')}")


@app.command("restore-book")
def restore_book(
    book_id: int = typer.Argument(...),
    db: Path = typer.Option(Path("mynovel.sqlite")),
) -> None:
    engine = create_engine_for_path(db)
    create_db_and_tables(engine)
    with Session(engine) as session:
        result = restore_to_latest_accepted_point(session, book_id)
    typer.echo(f"Restored book #{book_id} to chapter {result.restored_to_chapter}.")
