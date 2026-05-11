from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlmodel import Session

from mynovel.domain.models import VectorEntry, utc_now
from mynovel.domain.repositories import (
    list_vector_entries_for_book,
    list_vector_entries_for_source,
)


def index_text(
    session: Session,
    book_id: int,
    source_type: str,
    source_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    *,
    commit: bool = True,
) -> VectorEntry:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Indexed text cannot be empty.")

    for entry in list_vector_entries_for_source(session, book_id, source_type, source_id):
        session.delete(entry)

    vector_entry = VectorEntry(
        book_id=book_id,
        source_type=source_type,
        source_id=source_id,
        text=clean_text,
        embedding=dict(_token_counts(clean_text)),
        metadata_=metadata or {},
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
