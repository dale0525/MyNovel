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


class ChapterStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    NEEDS_REVISION = "needs_revision"
    ACCEPTED = "accepted"


class BlueprintStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CanonProposalRevisionStatus(StrEnum):
    RUNNING = "running"
    PENDING = "pending"
    APPLIED = "applied"
    DISCARDED = "discarded"
    STALE = "stale"
    FAILED = "failed"


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


class CanonProposalRevision(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    base_canon_version: int
    base_content_hash: str
    base_locks_hash: str
    target_section: str
    instruction: str
    allowed_sections: list = Field(default_factory=list, sa_column=Column(JSON))
    locked_sections: list = Field(default_factory=list, sa_column=Column(JSON))
    changed_sections: dict = Field(default_factory=dict, sa_column=Column(JSON))
    blocked_sections: list = Field(default_factory=list, sa_column=Column(JSON))
    summary: str = ""
    risks: list = Field(default_factory=list, sa_column=Column(JSON))
    status: CanonProposalRevisionStatus = CanonProposalRevisionStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    applied_at: datetime | None = None


class VolumePlan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    volume_number: int = Field(default=1, index=True)
    title: str
    core_conflict: str
    pacing_curve: list = Field(default_factory=list, sa_column=Column(JSON))
    payoff_distribution: list = Field(default_factory=list, sa_column=Column(JSON))
    key_turns: list = Field(default_factory=list, sa_column=Column(JSON))
    commitments: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Chapter(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    number: int = Field(index=True)
    title: str
    status: ChapterStatus = ChapterStatus.PLANNED
    plan: dict = Field(default_factory=dict, sa_column=Column(JSON))
    context_package: dict = Field(default_factory=dict, sa_column=Column(JSON))
    draft_text: str = ""
    revised_text: str = ""
    final_text: str = ""
    audit_report: dict = Field(default_factory=dict, sa_column=Column(JSON))
    state_delta: dict = Field(default_factory=dict, sa_column=Column(JSON))
    summary: str = ""
    reviewer_note: str | None = None
    word_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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


class VectorEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    source_type: str = Field(index=True)
    source_id: str = Field(index=True)
    text: str
    embedding: dict = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_: dict = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StyleAsset(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    name: str
    source_title: str | None = None
    source_excerpt: str
    fingerprint: dict = Field(default_factory=dict, sa_column=Column(JSON))
    guidance: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class DeconstructionStudy(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    source_title: str
    source_excerpt: str
    beat_map: list = Field(default_factory=list, sa_column=Column(JSON))
    craft_notes: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class QualitySnapshot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(index=True, foreign_key="book.id")
    score: float = 0.0
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSON))
    recommendations: list = Field(default_factory=list, sa_column=Column(JSON))
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
    parent_id: int | None = Field(default=None, index=True, foreign_key="openbookblueprint.id")
    idea: str
    version: int = 1
    status: BlueprintStatus = BlueprintStatus.PENDING
    instruction: str | None = None
    content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    raw_response: str = ""
    parse_error: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
