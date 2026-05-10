from pathlib import Path

import typer
from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.workflows.open_book import create_draft_book

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
