from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlmodel import Session

from mynovel.domain.models import (
    ChapterStatus,
    DeconstructionStudy,
    QualitySnapshot,
    StyleAsset,
)
from mynovel.domain.repositories import (
    add_deconstruction_study,
    add_quality_snapshot,
    add_style_asset,
    get_book,
    list_chapters_for_book,
    list_run_traces_for_book,
)
from mynovel.workflows.audit_issues import audit_issue_resolved


def create_style_asset(
    session: Session,
    book_id: int,
    name: str,
    reference_text: str,
    source_title: str | None = None,
) -> StyleAsset:
    _ensure_book(session, book_id)
    title = name.strip()
    text = reference_text.strip()
    if not title:
        raise ValueError("Style asset name cannot be empty.")
    if not text:
        raise ValueError("Style reference text cannot be empty.")

    fingerprint = _style_fingerprint(text)
    return add_style_asset(
        session,
        StyleAsset(
            book_id=book_id,
            name=title,
            source_title=source_title.strip() if source_title else None,
            source_excerpt=_excerpt(text),
            fingerprint=fingerprint,
            guidance=_style_guidance(fingerprint),
        ),
    )


def deconstruct_reference_text(
    session: Session,
    book_id: int,
    source_title: str,
    reference_text: str,
) -> DeconstructionStudy:
    _ensure_book(session, book_id)
    title = source_title.strip()
    text = reference_text.strip()
    if not title:
        raise ValueError("Reference title cannot be empty.")
    if not text:
        raise ValueError("Reference text cannot be empty.")

    beat_map = _beat_map(text)
    return add_deconstruction_study(
        session,
        DeconstructionStudy(
            book_id=book_id,
            source_title=title,
            source_excerpt=_excerpt(text),
            beat_map=beat_map,
            craft_notes=_craft_notes(beat_map),
        ),
    )


def generate_quality_snapshot(session: Session, book_id: int) -> QualitySnapshot:
    _ensure_book(session, book_id)
    chapters = list_chapters_for_book(session, book_id)
    traces = list_run_traces_for_book(session, book_id)
    metrics = _quality_metrics(chapters, traces)
    recommendations = _quality_recommendations(metrics)
    score = _quality_score(metrics)
    return add_quality_snapshot(
        session,
        QualitySnapshot(
            book_id=book_id,
            score=score,
            metrics=metrics,
            recommendations=recommendations,
        ),
    )


def recommend_cost_strategy(snapshot: QualitySnapshot) -> dict[str, Any]:
    metrics = snapshot.metrics
    if metrics.get("high_risk_issues", 0) > 0 or metrics.get("unresolved_issues", 0) > 1:
        return {
            "mode": "quality",
            "batch_limit": 1,
            "context_policy": "保留完整可信上下文，暂停批量推进直到风险处理完成。",
        }
    if metrics.get("estimated_chars", 0) > 20000 or metrics.get("review_backlog", 0) >= 5:
        return {
            "mode": "economy",
            "batch_limit": 3,
            "context_policy": "优先使用章节摘要和最近状态，减少重复上下文。",
        }
    return {
        "mode": "balanced",
        "batch_limit": 5,
        "context_policy": "保留关键人物、伏笔和最近章节摘要。",
    }


def _ensure_book(session: Session, book_id: int) -> None:
    if get_book(session, book_id) is None:
        raise ValueError("Book does not exist.")


def _style_fingerprint(text: str) -> dict[str, Any]:
    sentences = _sentences(text)
    paragraphs = _paragraphs(text)
    sentence_lengths = [len(sentence) for sentence in sentences] or [len(text)]
    dialogue_markers = text.count("“") + text.count("”") + text.count('"')
    sensory_terms = _count_terms(text, ("雾", "光", "声", "风", "雨", "冷", "热", "血", "夜"))
    return {
        "sentence_count": len(sentences),
        "paragraph_count": len(paragraphs),
        "average_sentence_chars": round(sum(sentence_lengths) / len(sentence_lengths), 1),
        "dialogue_marker_count": dialogue_markers,
        "sensory_term_count": sensory_terms,
        "keywords": _keywords(text),
    }


def _style_guidance(fingerprint: dict[str, Any]) -> dict[str, Any]:
    average = float(fingerprint.get("average_sentence_chars", 0))
    sentence_profile = "短句推进" if average <= 18 else "舒展叙述"
    sensory_density = "高感官密度" if fingerprint.get("sensory_term_count", 0) >= 3 else "克制描写"
    return {
        "sentence_profile": sentence_profile,
        "sensory_density": sensory_density,
        "style_rules": [
            f"保持{sentence_profile}，平均句长约 {average:.1f} 字。",
            f"维持{sensory_density}，避免无目的堆砌描写。",
            "章节结尾保留一个可追踪的新问题。",
        ],
    }


def _beat_map(text: str) -> list[dict[str, Any]]:
    labels = ("开局钩子", "冲突推进", "信息转折", "结尾承诺")
    paragraphs = _paragraphs(text)
    return [
        {
            "beat": labels[min(index, len(labels) - 1)],
            "summary": _excerpt(paragraph, 72),
            "position": index + 1,
        }
        for index, paragraph in enumerate(paragraphs)
    ]


def _craft_notes(beat_map: list[dict[str, Any]]) -> dict[str, Any]:
    opening = beat_map[0]["summary"] if beat_map else ""
    closing = beat_map[-1]["summary"] if beat_map else ""
    return {
        "opening_hook": opening,
        "closing_hook": closing,
        "reusable_moves": [
            "先给人物动作，再揭示异常信号。",
            "每段推进一个新信息，避免只解释设定。",
            "结尾把伏笔转成下一章问题。",
        ],
    }


def _quality_metrics(chapters: list, traces: list) -> dict[str, Any]:
    accepted = [chapter for chapter in chapters if chapter.status == ChapterStatus.ACCEPTED]
    backlog = [chapter for chapter in chapters if chapter.status == ChapterStatus.AWAITING_REVIEW]
    unresolved = 0
    high_risk = 0
    for chapter in chapters:
        audit_report = chapter.audit_report or {}
        chapter_is_high_risk = str(audit_report.get("risk_level", "")).lower() == "high"
        high_risk_issues = 0
        for issue in audit_report.get("issues", []):
            if not isinstance(issue, dict) or audit_issue_resolved(issue):
                continue
            unresolved += 1
            if str(issue.get("severity", "")).lower() == "high":
                high_risk_issues += 1
        high_risk += max(1 if chapter_is_high_risk else 0, high_risk_issues)

    estimated_chars = sum(
        int(trace.cost.get("prompt_chars", 0)) + int(trace.cost.get("completion_chars", 0))
        for trace in traces
    )
    accepted_word_counts = [chapter.word_count for chapter in accepted if chapter.word_count]
    average_word_count = (
        round(sum(accepted_word_counts) / len(accepted_word_counts), 1)
        if accepted_word_counts
        else 0
    )
    return {
        "accepted_chapters": len(accepted),
        "review_backlog": len(backlog),
        "high_risk_issues": high_risk,
        "unresolved_issues": unresolved,
        "average_word_count": average_word_count,
        "estimated_chars": estimated_chars,
        "trace_count": len(traces),
    }


def _quality_score(metrics: dict[str, Any]) -> float:
    score = 100
    score -= int(metrics.get("high_risk_issues", 0)) * 25
    score -= int(metrics.get("unresolved_issues", 0)) * 8
    score -= int(metrics.get("review_backlog", 0)) * 2
    score += min(10, int(metrics.get("accepted_chapters", 0)) * 2)
    return float(max(0, min(100, score)))


def _quality_recommendations(metrics: dict[str, Any]) -> list[str]:
    recommendations = []
    if metrics.get("high_risk_issues", 0):
        recommendations.append("存在高风险问题，先处理人工审核再继续批量生产。")
    if metrics.get("unresolved_issues", 0):
        recommendations.append("仍有未解决审计项，优先让系统修复或退回重写。")
    if metrics.get("review_backlog", 0) >= 3:
        recommendations.append("待审核章节较多，先清理审核队列再继续生成。")
    if metrics.get("estimated_chars", 0) > 20000:
        recommendations.append("上下文成本偏高，建议改用摘要和最近状态控制成本。")
    if not recommendations:
        recommendations.append("质量状态稳定，可以继续按当前节奏生产。")
    return recommendations


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"[。！？!?]+", text) if item.strip()]


def _paragraphs(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]


def _keywords(text: str) -> list[str]:
    terms = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    counter: Counter[str] = Counter()
    for term in terms:
        for index in range(max(1, len(term) - 1)):
            counter[term[index : index + 2]] += 1
    return [item for item, _ in counter.most_common(6)]


def _count_terms(text: str, terms: tuple[str, ...]) -> int:
    return sum(text.count(term) for term in terms)


def _excerpt(text: str, limit: int = 120) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit]
