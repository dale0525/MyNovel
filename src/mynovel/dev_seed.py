from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlmodel import Session, select

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import (
    Book,
    BookStatus,
    BlueprintStatus,
    Canon,
    Chapter,
    ChapterStatus,
    OpenBookBlueprint,
    ProviderConfig,
    RunTrace,
    VolumePlan,
)


def _orm(value: object) -> Any:
    return cast(Any, value)


def ensure_dev_demo_data(db_path: Path) -> None:
    engine = create_engine_for_path(db_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        _ensure_provider_config(session)
        blueprint = _ensure_blueprint(session)
        book = _ensure_book(session)
        _ensure_canon(session, book)
        _ensure_volume_plan(session, book)
        _ensure_chapters(session, book)
        _ensure_traces(session, book)
        session.add(blueprint)
        session.commit()


def _ensure_provider_config(session: Session) -> None:
    if session.get(ProviderConfig, 1) is not None:
        return
    session.add(
        ProviderConfig(
            id=1,
            llm_base_url="https://api.example.test/v1",
            llm_api_key="local-demo-key",
            llm_model="gpt-4o-mini",
            embedding_use_llm_credentials=True,
            embedding_base_url="",
            embedding_model="text-embedding-3-small",
            rerank_use_llm_credentials=True,
            rerank_base_url="",
            rerank_model="bge-reranker-v2-m3",
        )
    )


def _ensure_blueprint(session: Session) -> OpenBookBlueprint:
    existing = session.exec(
        select(OpenBookBlueprint).order_by(_orm(OpenBookBlueprint.id).desc()).limit(1)
    ).first()
    if existing is not None:
        existing.idea = "少年在雾谷边境发现古老召唤符号，被迫踏入失落王朝的遗迹。"
        existing.status = BlueprintStatus.SUCCEEDED
        existing.content = _blueprint_content()
        existing.raw_response = "{}"
        existing.parse_error = None
        existing.error_message = None
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    blueprint = OpenBookBlueprint(
        idea="少年在雾谷边境发现古老召唤符号，被迫踏入失落王朝的遗迹。",
        version=1,
        status=BlueprintStatus.SUCCEEDED,
        content=_blueprint_content(),
        raw_response="{}",
    )
    session.add(blueprint)
    session.commit()
    session.refresh(blueprint)
    return blueprint


def _ensure_book(session: Session) -> Book:
    existing = session.exec(select(Book).order_by(_orm(Book.id)).limit(1)).first()
    if existing is None:
        book = Book(
            title="幽谷回声",
            genre="奇幻连载",
            audience="成长冒险读者",
            status=BookStatus.PRODUCING,
            premise="少年罗斯在幽谷边境听见远古召唤，发现自己与失落王朝有关。",
            constraints={"selling_points": ["遗迹探索", "身份谜团", "章节钩子"]},
        )
        session.add(book)
        session.commit()
        session.refresh(book)
        return book

    existing.title = "幽谷回声"
    existing.genre = "奇幻连载"
    existing.audience = "成长冒险读者"
    existing.status = BookStatus.PRODUCING
    existing.premise = "少年罗斯在幽谷边境听见远古召唤，发现自己与失落王朝有关。"
    existing.constraints = {"selling_points": ["遗迹探索", "身份谜团", "章节钩子"]}
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def _ensure_canon(session: Session, book: Book) -> None:
    if book.id is None:
        return
    existing = session.exec(select(Canon).where(Canon.book_id == book.id).limit(1)).first()
    if existing is not None:
        return
    session.add(
        Canon(
            book_id=book.id,
            version=2,
            content={
                "book": {"title": book.title, "genre": book.genre, "audience": book.audience},
                "world_rules": [
                    {"name": "雾墙规则", "detail": "幽谷的雾会吞没没有符号护持的人。"},
                    {"name": "召唤符号", "detail": "符号只回应被失落王朝血脉触碰的人。"},
                ],
                "characters": [
                    {"name": "罗斯", "detail": "石匠学徒，触发召唤符号。"},
                    {"name": "莉拉", "detail": "边境药师，熟悉古语和遗迹传闻。"},
                ],
                "locations": [{"name": "幽谷", "detail": "旧王朝遗迹与边境村落交界。"}],
                "relationships": [{"from": "罗斯", "to": "莉拉", "detail": "临时同盟。"}],
                "foreshadowing": ["石门后的第二枚符号尚未解释。"],
                "chapter_summaries": [
                    {"chapter": 1, "title": "召唤", "summary": "罗斯触碰符号并听见雾中的回应。"}
                ],
                "state_history": [
                    {
                        "chapter": 1,
                        "changes": [{"type": "人物状态", "target": "罗斯", "change": "进入幽谷"}],
                    }
                ],
            },
        )
    )


def _ensure_volume_plan(session: Session, book: Book) -> None:
    if book.id is None:
        return
    existing = session.exec(
        select(VolumePlan).where(VolumePlan.book_id == book.id).limit(1)
    ).first()
    if existing is not None:
        return
    session.add(
        VolumePlan(
            book_id=book.id,
            volume_number=1,
            title="第一卷：雾谷回声",
            core_conflict="罗斯要确认召唤来源，同时避开边境守军和旧王朝残留势力。",
            pacing_curve=["触发召唤", "进入遗迹", "识别追兵", "打开石门"],
            payoff_distribution=["每章发现一个新符号", "每三章揭示一次身份线索"],
            key_turns=["莉拉加入", "守军封谷", "石门开启"],
            commitments=["遗迹谜题", "身份成长", "章节末尾钩子"],
        )
    )


def _ensure_chapters(session: Session, book: Book) -> None:
    if book.id is None:
        return
    existing = list(session.exec(select(Chapter).where(Chapter.book_id == book.id)))
    if len(existing) >= 10:
        return
    for chapter in existing:
        session.delete(chapter)
    session.flush()
    for chapter in _demo_chapters(book.id):
        session.add(chapter)


def _ensure_traces(session: Session, book: Book) -> None:
    if book.id is None:
        return
    existing = session.exec(select(RunTrace).where(RunTrace.book_id == book.id).limit(1)).first()
    if existing is not None:
        return
    session.add(
        RunTrace(
            book_id=book.id,
            stage="chapter_pipeline",
            model="本地演示模型",
            cost={"estimated": 0.18},
            metadata_={"chapter": 2, "status": "awaiting_review"},
        )
    )


def _demo_chapters(book_id: int) -> list[Chapter]:
    titles = [
        "召唤",
        "穿越迷雾",
        "隐秘小径",
        "废墟中的低语",
        "破碎之门",
        "谷底深处",
        "遗落的祠堂",
        "月影之约",
        "守夜人",
        "风声再起",
    ]
    chapters = []
    for index, title in enumerate(titles, start=1):
        status = ChapterStatus.PLANNED
        draft = ""
        revised = ""
        final = ""
        summary = ""
        audit_report = {}
        state_delta = {}
        if index == 1:
            status = ChapterStatus.ACCEPTED
            final = _accepted_text()
            revised = final
            summary = "罗斯触碰符号，第一次听见幽谷深处的召唤。"
            state_delta = {
                "changes": [{"type": "人物状态", "target": "罗斯", "change": "触发召唤符号"}]
            }
        elif index == 2:
            status = ChapterStatus.AWAITING_REVIEW
            revised = _review_text()
            draft = revised
            summary = "罗斯和莉拉进入雾墙，发现第二枚符号。"
            audit_report = {
                "risk_level": "medium",
                "issues": [
                    {"severity": "medium", "title": "角色动机需要再明确", "resolved": True},
                    {"severity": "low", "title": "伏笔提示略密", "resolved": False},
                ],
            }
            state_delta = {
                "changes": [
                    {"type": "地点", "target": "幽谷雾墙", "change": "首次进入"},
                    {"type": "伏笔", "target": "第二枚符号", "change": "露出但未解释"},
                ]
            }
        elif index == 3:
            status = ChapterStatus.RUNNING
            draft = "罗斯沿着隐秘小径继续向前，雾里传来像钟声一样的回响。"
            summary = "正在生成草稿。"
        chapters.append(
            Chapter(
                book_id=book_id,
                number=index,
                title=title,
                status=status,
                plan={
                    "goal": f"推进第 {index:02d} 章的遗迹探索，并保留结尾钩子。",
                    "ending_hook": "留出一个新的危险或答案缺口。",
                },
                draft_text=draft,
                revised_text=revised,
                final_text=final,
                audit_report=audit_report,
                state_delta=state_delta,
                summary=summary,
                word_count=len(final or revised or draft),
            )
        )
    return chapters


def _blueprint_content() -> dict:
    return {
        "title_options": ["幽谷回声", "碎光纪元", "潮汐尽头"],
        "genre": "奇幻连载",
        "audience": "喜欢探索、成长和身份谜团的读者",
        "selling_points": ["遗迹谜题", "少年成长", "章节钩子"],
        "protagonist": {"name": "罗斯", "hook": "能听见失落王朝召唤的石匠学徒"},
        "world": {"premise": "雾谷封存着旧王朝遗迹，符号会选择继承者。"},
        "central_conflict": "罗斯必须查清召唤来源，同时躲避想夺走符号的人。",
        "reader_promises": ["每章推进一个遗迹谜题", "持续揭示罗斯身世"],
        "chapter_directions": [
            {"chapter": "第 01 章", "direction": "触发召唤符号"},
            {"chapter": "第 02 章", "direction": "进入幽谷雾墙"},
            {"chapter": "第 03 章", "direction": "发现隐秘小径"},
        ],
    }


def _accepted_text() -> str:
    return (
        "山谷在晨雾中苏醒。石拱桥像一条沉睡的脊梁，横卧在溪流之上。\n\n"
        "罗斯站在桥头，手心微微出汗。背后的村庄很小，炊烟像被风揉散的白线。\n\n"
        "他低头看了一眼掌心的符号。它亮了一瞬，像是在回应雾谷深处的呼唤。"
    )


def _review_text() -> str:
    return (
        "薄雾在峡谷间流动，像一层轻纱，将世界与远处隔开。\n\n"
        "莉拉紧了紧披风，沿着碎石路缓缓向上。罗斯跟在她身后，"
        "指尖的符号一阵阵发热。\n\n"
        "前方，断裂的拱门半立在草丛里，石缝里缠绕着常春藤。"
        "门中央刻着模糊的符号，像古老文字，又像某种被遗忘的语言。"
    )
