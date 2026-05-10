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
    embedding_use_llm_credentials: bool = True
    embedding_base_url: str
    embedding_api_key: str | None = None
    embedding_model: str
    rerank_use_llm_credentials: bool = True
    rerank_base_url: str | None = None
    rerank_api_key: str | None = None
    rerank_model: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def resolved_embedding_base_url(self) -> str:
        if self.embedding_use_llm_credentials:
            return self.llm_base_url
        return self.embedding_base_url

    def resolved_embedding_api_key(self) -> str | None:
        if self.embedding_use_llm_credentials:
            return self.llm_api_key
        return self.embedding_api_key

    def resolved_rerank_base_url(self) -> str | None:
        if self.rerank_use_llm_credentials:
            return self.llm_base_url
        return self.rerank_base_url

    def resolved_rerank_api_key(self) -> str | None:
        if self.rerank_use_llm_credentials:
            return self.llm_api_key
        return self.rerank_api_key


class OpenBookBlueprint(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    idea: str
    version: int = 1
    instruction: str | None = None
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    raw_response: str
    parse_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
