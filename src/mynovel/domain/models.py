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


class ProviderConfig(SQLModel, table=True):
    id: int | None = Field(default=1, primary_key=True)
    llm_base_url: str
    llm_api_key: str | None = None
    llm_model: str
    embedding_base_url: str
    embedding_api_key: str | None = None
    embedding_model: str
    rerank_base_url: str | None = None
    rerank_api_key: str | None = None
    rerank_model: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
