from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from math import sqrt
from typing import Any

from sqlmodel import Session

from mynovel.domain.models import VectorEntry, utc_now
from mynovel.domain.repositories import (
    list_vector_entries_for_book,
    list_vector_entries_for_source,
)

DEFAULT_RETRIEVAL_TOP_K = 10
DEFAULT_RETRIEVAL_CHARACTER_BUDGET = 10000


@dataclass(frozen=True)
class RetrievedContext:
    source_type: str
    source_id: str
    score: float
    text: str
    metadata: dict[str, Any]


def index_text(
    session: Session,
    book_id: int,
    source_type: str,
    source_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    *,
    embedding_vector: list[float] | None = None,
    embedding_model: str | None = None,
    embedding_error: str | None = None,
    commit: bool = True,
) -> VectorEntry:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Indexed text cannot be empty.")

    for entry in list_vector_entries_for_source(session, book_id, source_type, source_id):
        session.delete(entry)

    entry_metadata = dict(metadata or {})
    if embedding_vector is not None and embedding_model:
        vector = [float(value) for value in embedding_vector]
        embedding: Any = vector
        entry_metadata.update(
            {
                "embedding_kind": "model",
                "embedding_model": embedding_model,
                "embedding_dimensions": len(vector),
            }
        )
    else:
        embedding = dict(_token_counts(clean_text))
        entry_metadata["embedding_kind"] = "lexical"
        if embedding_error:
            entry_metadata["embedding_error"] = embedding_error

    vector_entry = VectorEntry(
        book_id=book_id,
        source_type=source_type,
        source_id=source_id,
        text=clean_text,
        embedding=embedding,
        metadata_=entry_metadata,
        updated_at=utc_now(),
    )
    session.add(vector_entry)
    if commit:
        session.commit()
        session.refresh(vector_entry)
    else:
        session.flush()
    return vector_entry


def search_book_context(
    session: Session,
    book_id: int,
    query: str,
    limit: int = 6,
) -> list[VectorEntry]:
    query_text = query.strip()
    if not query_text:
        return []

    query_counts = _token_counts(query_text)
    scored_entries = []
    for entry in list_vector_entries_for_book(session, book_id):
        score = _score_entry(query_counts, entry)
        if score > 0:
            scored_entries.append((score, entry))

    scored_entries.sort(key=lambda item: (-item[0], item[1].created_at, item[1].id or 0))
    return [entry for _, entry in scored_entries[:limit]]


def retrieve_book_context(
    session: Session,
    book_id: int,
    query: str,
    *,
    query_embedding: list[float] | None = None,
    embedding_model: str | None = None,
    top_k: int = DEFAULT_RETRIEVAL_TOP_K,
    character_budget: int = DEFAULT_RETRIEVAL_CHARACTER_BUDGET,
) -> list[RetrievedContext]:
    query_vector = _numeric_vector(query_embedding)
    if query_vector and embedding_model:
        return _retrieve_model_context(
            session,
            book_id,
            query_vector,
            embedding_model,
            top_k,
            character_budget,
        )

    query_counts = _token_counts(query.strip())
    contexts: list[RetrievedContext] = []
    for entry in search_book_context(session, book_id, query, limit=top_k):
        contexts.append(
            RetrievedContext(
                source_type=entry.source_type,
                source_id=entry.source_id,
                score=_score_entry(query_counts, entry),
                text=entry.text,
                metadata=dict(entry.metadata_ or {}),
            )
        )
    return _apply_retrieval_bounds(contexts, top_k, character_budget)


def _retrieve_model_context(
    session: Session,
    book_id: int,
    query_vector: list[float],
    embedding_model: str,
    top_k: int,
    character_budget: int,
) -> list[RetrievedContext]:
    scored_contexts: list[RetrievedContext] = []
    for entry in list_vector_entries_for_book(session, book_id):
        metadata = dict(entry.metadata_ or {})
        if metadata.get("embedding_model") != embedding_model:
            continue
        entry_vector = _numeric_vector(entry.embedding)
        if entry_vector is None or len(entry_vector) != len(query_vector):
            continue
        score = _cosine_similarity(query_vector, entry_vector)
        if score is None:
            continue
        scored_contexts.append(
            RetrievedContext(
                source_type=entry.source_type,
                source_id=entry.source_id,
                score=score,
                text=entry.text,
                metadata=metadata,
            )
        )

    scored_contexts.sort(key=lambda context: -context.score)
    return _apply_retrieval_bounds(scored_contexts, top_k, character_budget)


def _apply_retrieval_bounds(
    contexts: list[RetrievedContext],
    top_k: int,
    character_budget: int,
) -> list[RetrievedContext]:
    if top_k <= 0 or character_budget <= 0:
        return []

    bounded: list[RetrievedContext] = []
    used_characters = 0
    for context in contexts:
        if len(bounded) >= top_k:
            break
        next_total = used_characters + len(context.text)
        if next_total > character_budget:
            break
        bounded.append(context)
        used_characters = next_total
    return bounded


def _numeric_vector(value: Any) -> list[float] | None:
    if not isinstance(value, list) or not value:
        return None
    vector: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int | float):
            return None
        vector.append(float(item))
    return vector


def _cosine_similarity(left: list[float], right: list[float]) -> float | None:
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return None
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    return dot_product / (left_norm * right_norm)


def _score_entry(query_counts: Counter[str], entry: VectorEntry) -> float:
    entry_counts = Counter(entry.embedding or _token_counts(entry.text))
    score = sum(weight * entry_counts.get(token, 0) for token, weight in query_counts.items())
    query_terms = [token for token in query_counts if len(token) >= 2]
    score += sum(4 for term in query_terms if term in entry.text)
    return float(score)


def _token_counts(text: str) -> Counter[str]:
    tokens: list[str] = []
    for segment in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text.lower()):
        if _is_cjk_segment(segment):
            tokens.extend(segment)
            for size in (2, 3, 4):
                tokens.extend(
                    segment[index : index + size] for index in range(len(segment) - size + 1)
                )
        else:
            tokens.append(segment)
    return Counter(tokens)


def _is_cjk_segment(value: str) -> bool:
    return bool(value) and all("\u4e00" <= char <= "\u9fff" for char in value)
