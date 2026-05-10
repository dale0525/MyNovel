from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BookStatus(StrEnum):
    DRAFT = "draft"
    CANON_LOCKED = "canon_locked"
    PRODUCING = "producing"
    PAUSED = "paused"


class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    genre: str
    audience: str
    status: BookStatus = BookStatus.DRAFT
    premise: str | None = None
    constraints: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Canon(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    version: int = 1
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class RunTrace(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int | None = Field(default=None, index=True, foreign_key="book.id")
    stage: str
    prompt_id: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    cost: dict = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_: dict = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    created_at: datetime = Field(default_factory=utc_now)
