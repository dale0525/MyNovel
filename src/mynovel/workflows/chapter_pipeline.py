from __future__ import annotations

from copy import deepcopy

from sqlmodel import Session

from mynovel.domain.models import BookStatus, Canon, Chapter, ChapterStatus, RunTrace, utc_now
from mynovel.domain.repositories import get_book, get_chapter, get_latest_canon


def run_chapter_pipeline(session: Session, chapter_id: int) -> Chapter:
    chapter = _required_chapter(session, chapter_id)
    book = get_book(session, chapter.book_id)
    canon = get_latest_canon(session, chapter.book_id)
    if book is None or canon is None:
        raise ValueError("Chapter must belong to a book with trusted state.")

    chapter.status = ChapterStatus.RUNNING
    chapter.context_package = _build_context_package(canon, chapter)
    chapter.draft_text = _generate_draft_text(book.title, chapter)
    chapter.audit_report = _audit_chapter(chapter)
    chapter.revised_text = _revise_text(chapter.draft_text, chapter.audit_report)
    chapter.state_delta = _extract_state_delta(chapter)
    chapter.summary = _summarize_chapter(chapter)
    chapter.word_count = len(chapter.revised_text)
    chapter.status = ChapterStatus.AWAITING_REVIEW
    chapter.updated_at = utc_now()
    book.status = BookStatus.PRODUCING

    session.add(book)
    session.add(chapter)
    session.add(
        RunTrace(
            book_id=chapter.book_id,
            stage="chapter_pipeline",
            model="local-product-simulator",
            cost={"estimated": 0},
            metadata_={"chapter": chapter.number, "status": chapter.status.value},
        )
    )
    session.commit()
    session.refresh(chapter)
    return chapter


def approve_chapter(session: Session, chapter_id: int, reviewer_note: str | None = None) -> Chapter:
    chapter = _required_chapter(session, chapter_id)
    latest = get_latest_canon(session, chapter.book_id)
    if latest is None:
        raise ValueError("Trusted state is required before accepting a chapter.")
    if chapter.status != ChapterStatus.AWAITING_REVIEW:
        raise ValueError("Only chapters waiting for human review can be accepted.")

    chapter.status = ChapterStatus.ACCEPTED
    chapter.final_text = chapter.revised_text or chapter.draft_text
    chapter.reviewer_note = reviewer_note
    chapter.updated_at = utc_now()

    updated_content = _content_with_accepted_chapter(latest.content, chapter)
    session.add(chapter)
    session.add(Canon(book_id=chapter.book_id, version=latest.version + 1, content=updated_content))
    session.add(
        RunTrace(
            book_id=chapter.book_id,
            stage="accept_chapter",
            model=None,
            cost={"estimated": 0},
            metadata_={"chapter": chapter.number, "trusted_state_version": latest.version + 1},
        )
    )
    session.commit()
    session.refresh(chapter)
    return chapter


def _required_chapter(session: Session, chapter_id: int) -> Chapter:
    chapter = get_chapter(session, chapter_id)
    if chapter is None:
        raise ValueError("Chapter does not exist.")
    return chapter


def _build_context_package(canon: Canon, chapter: Chapter) -> dict:
    return {
        "trusted_state": {
            "version": canon.version,
            "book": canon.content.get("book", {}),
            "characters": canon.content.get("characters", []),
            "foreshadowing": canon.content.get("foreshadowing", []),
            "chapter_summaries": canon.content.get("chapter_summaries", []),
        },
        "chapter_goal": chapter.plan.get("goal", ""),
        "must_write": chapter.plan.get("must_write", []),
        "forbidden_drift": ["不要改写已锁定设定", "不要让状态变化绕过人工审核"],
    }


def _generate_draft_text(book_title: str, chapter: Chapter) -> str:
    goal = chapter.plan.get("goal") or "推进本章目标。"
    return (
        f"《{book_title}》第 {chapter.number:02d} 章：{chapter.title}\n\n"
        f"{goal}\n\n"
        "雾气贴着山谷缓慢流动，像一层尚未揭开的旧纸。主角沿着潮湿石阶向前，"
        "每一步都把熟悉的生活留在身后。远处传来低低的回响，仿佛有人在破碎的墙后"
        "读出一段被抹去的历史。\n\n"
        "她停下脚步，确认那枚符号仍在掌心发热。它不是答案，更像一道邀请。"
        "如果继续向前，她会失去安全的退路；如果回头，真相也会从此沉入雾中。"
    )


def _audit_chapter(chapter: Chapter) -> dict:
    return {
        "risk_level": "medium",
        "issues": [
            {"severity": "medium", "title": "人物动机需要更明确", "resolved": True},
            {"severity": "low", "title": "环境描写略有重复", "resolved": True},
            {"severity": "medium", "title": "结尾钩子需要更强", "resolved": False},
        ],
        "suggestions": ["强化主角继续前进的理由", "把最后一句改成新的悬念"],
    }


def _revise_text(draft_text: str, audit_report: dict) -> str:
    unresolved = [
        issue["title"]
        for issue in audit_report.get("issues", [])
        if isinstance(issue, dict) and not issue.get("resolved")
    ]
    hook = "石门深处忽然亮起第二枚符号，像是在回应她掌心的热度。"
    if unresolved:
        return f"{draft_text}\n\n修订后钩子：{hook}"
    return draft_text


def _extract_state_delta(chapter: Chapter) -> dict:
    return {
        "chapter": chapter.number,
        "changes": [
            {"type": "人物状态", "target": "主角", "change": "离开安全区，主动追查真相"},
            {"type": "地点", "target": chapter.title, "change": "首次进入本章关键地点"},
            {"type": "伏笔", "target": "发热符号", "change": "符号与遗迹产生呼应"},
        ],
    }


def _summarize_chapter(chapter: Chapter) -> str:
    return f"第 {chapter.number:02d} 章《{chapter.title}》完成本章目标，并留下新的遗迹线索。"


def _content_with_accepted_chapter(content: dict, chapter: Chapter) -> dict:
    updated = deepcopy(content)
    updated.setdefault("chapter_summaries", []).append(
        {
            "chapter": chapter.number,
            "title": chapter.title,
            "summary": chapter.summary,
            "word_count": chapter.word_count,
        }
    )
    updated.setdefault("state_history", []).append(chapter.state_delta)
    updated.setdefault("accepted_chapters", []).append(
        {"chapter": chapter.number, "title": chapter.title, "accepted_at": utc_now().isoformat()}
    )
    return updated
