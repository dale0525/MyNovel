from __future__ import annotations

from typing import Any

from mynovel.domain.models import Canon, Chapter
from mynovel.word_targets import parse_word_count


def build_plan_messages(
    book_title: str,
    canon: Canon,
    chapter: Chapter,
    volume_plan: dict[str, Any],
) -> list[dict[str, str]]:
    body = _join_prompt_sections(
        [
            f"作品：{book_title}",
            _chapter_heading(chapter),
            _chapter_direction_text(chapter),
            _volume_plan_text(volume_plan, chapter.number),
            _trusted_state_text(canon.content),
        ]
    )
    return _json_instruction_messages(
        "你是网文章节导演。请为当前章节生成可执行的章节计划，只输出 JSON。",
        "必须包含 goal, must_write, forbidden_drift, word_budget, ending_hook。"
        "如果下方已有目标字数，word_budget 必须沿用该数值。",
        body,
    )


def build_draft_messages(book_title: str, chapter: Chapter) -> list[dict[str, str]]:
    body = _join_prompt_sections(
        [
            f"作品：{book_title}",
            _chapter_heading(chapter),
            _chapter_plan_text(chapter.plan),
            _context_package_text(chapter.context_package, chapter.number),
        ]
    )
    return _text_instruction_messages(
        "你是网文连载正文生成器。根据章节计划和可信上下文写本章草稿。",
        "只输出章节正文，不要解释，不要附加元信息。",
        body,
    )


def build_extract_state_messages(chapter: Chapter) -> list[dict[str, str]]:
    body = _join_prompt_sections(
        [
            _chapter_heading(chapter),
            _chapter_plan_text(chapter.plan),
            "待提取正文：\n" + chapter.draft_text,
        ]
    )
    return _json_instruction_messages(
        "你是小说状态变化提取器。从草稿提取待人工验证的状态变化，只输出 JSON。",
        "必须包含 chapter 与 changes。changes 只记录人物、关系、地点、资源、伏笔和信息暴露变化。",
        body,
    )


def build_audit_messages(chapter: Chapter) -> list[dict[str, str]]:
    body = _join_prompt_sections(
        [
            _chapter_heading(chapter),
            _chapter_plan_text(chapter.plan),
            _context_package_text(chapter.context_package, chapter.number),
            _state_delta_text(chapter.state_delta),
            "待审计正文：\n" + chapter.draft_text,
        ]
    )
    return _json_instruction_messages(
        "你是连载章节审计员。检查连续性、因果、动机、伏笔、节奏、字数和结尾钩子，只输出 JSON。",
        "必须包含 risk_level, issues, suggestions。issues 内每项包含 severity, title, resolved。"
        "不要输出 Markdown、表格、标题或解释。",
        body,
    )


def build_revise_messages(chapter: Chapter) -> list[dict[str, str]]:
    body = _join_prompt_sections(
        [
            _chapter_heading(chapter),
            _chapter_plan_text(chapter.plan),
            _revision_word_count_text(chapter),
            _audit_report_text(chapter.audit_report or {}),
            "待修订正文：\n" + chapter.draft_text,
        ]
    )
    return _text_instruction_messages(
        "你是连载章节修订器。根据审计报告修订正文，尽量解决可自动修复的问题。",
        "只输出修订后的最终候选正文，不要解释。",
        body,
    )


def _json_instruction_messages(
    system_prompt: str,
    schema_prompt: str,
    body: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"{schema_prompt}\n\n{body}",
        },
    ]


def _text_instruction_messages(
    system_prompt: str,
    instruction: str,
    body: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"{instruction}\n\n{body}",
        },
    ]


def _chapter_heading(chapter: Chapter) -> str:
    return f"本章：第 {chapter.number:02d} 章《{chapter.title}》"


def _chapter_direction_text(chapter: Chapter) -> str:
    lines = []
    goal = str(chapter.plan.get("goal") or "").strip()
    if goal:
        lines.append(f"已有方向：{goal}")
    word_budget = parse_word_count(chapter.plan.get("word_budget"))
    if word_budget is not None:
        lines.append(f"已有目标字数：{word_budget} 字")
    if not lines:
        lines.append("已有方向：沿用本章标题和卷纲推进。")
    return "本章已知要求：\n" + "\n".join(lines)


def _chapter_plan_text(plan: dict[str, Any]) -> str:
    lines: list[str] = []
    goal = str(plan.get("goal") or "").strip()
    if goal:
        lines.append(f"本章目标：{goal}")
    word_budget = parse_word_count(plan.get("word_budget"))
    if word_budget is not None:
        lines.append(f"目标字数：{word_budget} 字")
    lines.extend(_list_block("必须写", plan.get("must_write")))
    lines.extend(_list_block("禁止偏移", plan.get("forbidden_drift")))
    ending_hook = str(plan.get("ending_hook") or "").strip()
    if ending_hook:
        lines.append(f"结尾钩子：{ending_hook}")
    return "章节计划：\n" + "\n".join(lines or ["按本章标题推进，避免改写已锁定设定。"])


def _context_package_text(context_package: dict[str, Any], chapter_number: int) -> str:
    sections = [
        _trusted_state_text(context_package.get("trusted_state", {})),
        _volume_plan_text(context_package.get("volume_plan", {}), chapter_number),
        _retrieved_context_text(context_package.get("retrieved_context")),
    ]
    chapter_goal = str(context_package.get("chapter_goal") or "").strip()
    if chapter_goal:
        sections.append("上下文补充：\n" + f"- 本章目标：{chapter_goal}")
    return _join_prompt_sections(sections)


def _trusted_state_text(content: dict[str, Any]) -> str:
    lines: list[str] = []
    book = content.get("book")
    if isinstance(book, dict):
        lines.extend(_book_lines(book))
    lines.extend(
        _entity_lines("关键人物", content.get("characters"), ("name", "identity", "motivation"), 8)
    )
    lines.extend(
        _entity_lines("近期关系", content.get("relationships"), ("name", "detail", "type"), 5)
    )
    lines.extend(_entity_lines("关键地点", content.get("locations"), ("name", "detail", "type"), 5))
    lines.extend(_entity_lines("资源道具", content.get("resources"), ("name", "detail", "type"), 5))
    lines.extend(
        _entity_lines("伏笔线索", content.get("foreshadowing"), ("description", "trigger"), 6)
    )
    lines.extend(_chapter_summary_lines(content.get("chapter_summaries")))
    return "可信设定摘要：\n" + "\n".join(lines or ["- 暂无可信设定摘要。"])


def _volume_plan_text(volume_plan: dict[str, Any], chapter_number: int) -> str:
    if not isinstance(volume_plan, dict) or not volume_plan:
        return "卷纲摘要：\n- 暂无卷纲。"
    lines: list[str] = []
    title = str(volume_plan.get("title") or "").strip()
    if title:
        lines.append(f"- 分卷：{title}")
    core_conflict = str(volume_plan.get("core_conflict") or "").strip()
    if core_conflict:
        lines.append(f"- 核心冲突：{core_conflict}")
    pacing = _current_pacing_line(volume_plan.get("pacing_curve"), chapter_number)
    if pacing:
        lines.append(pacing)
    commitments = volume_plan.get("commitments")
    if isinstance(commitments, list) and commitments:
        commitment_text = "；".join(
            str(item).strip() for item in commitments[:4] if str(item).strip()
        )
        if commitment_text:
            lines.append("- 承诺：" + commitment_text)
    return "卷纲摘要：\n" + "\n".join(lines or ["- 暂无卷纲。"])


def _current_pacing_line(pacing_curve: object, chapter_number: int) -> str:
    if not isinstance(pacing_curve, list) or not pacing_curve:
        return ""
    index = min(max(chapter_number - 1, 0), len(pacing_curve) - 1)
    item = pacing_curve[index]
    if not isinstance(item, dict):
        return ""
    title = str(item.get("title") or "").strip()
    goal = str(item.get("goal") or "").strip()
    if title and goal:
        return f"- 当前节拍：{title}：{goal}"
    if title:
        return f"- 当前节拍：{title}"
    if goal:
        return f"- 当前节拍：{goal}"
    return ""


def _state_delta_text(state_delta: dict[str, Any]) -> str:
    changes = state_delta.get("changes") if isinstance(state_delta, dict) else None
    if not isinstance(changes, list) or not changes:
        return "候选状态变化：\n- 暂无候选状态变化。"
    lines = []
    for change in changes[:12]:
        if not isinstance(change, dict):
            continue
        parts = [
            str(change.get("type") or "").strip(),
            str(change.get("target") or "").strip(),
            str(change.get("change") or change.get("description") or "").strip(),
        ]
        line = " / ".join(part for part in parts if part)
        if line:
            lines.append(f"- {line}")
    return "候选状态变化：\n" + "\n".join(lines or ["- 暂无候选状态变化。"])


def _retrieved_context_text(items: object) -> str:
    if not isinstance(items, list) or not items:
        return ""

    priority = "可信设定优先于历史召回片段；当两者冲突时，忽略召回片段。"
    lines = ["历史召回片段：", priority]
    for index, item in enumerate(items[:6], start=1):
        if not isinstance(item, dict):
            text = str(item).strip()[:1200]
            if text:
                lines.append(f"- 片段 {index}：{text}")
            continue
        source_label = _retrieved_source_label(item)
        score = item.get("score")
        score_text = f"，相关度 {score}" if isinstance(score, int | float) else ""
        text = str(item.get("text") or "").strip()[:1200]
        if not text:
            continue
        lines.append(f"- 片段 {index}（{source_label}{score_text}）：{text}")
        metadata_line = _retrieved_metadata_line(item.get("metadata"))
        if metadata_line:
            lines.append(f"  - 线索：{metadata_line}")
    if len(lines) == 2:
        return ""
    return "\n".join(lines)


def _retrieved_source_label(item: dict[str, Any]) -> str:
    source_type = str(item.get("source_type") or "历史资料").strip()
    source_id = str(item.get("source_id") or "").strip()
    if source_id:
        return f"{source_type} {source_id}"
    return source_type


def _retrieved_metadata_line(metadata: object) -> str:
    if not isinstance(metadata, dict):
        return ""
    labels = []
    for key, label in (
        ("kind", "类型"),
        ("chapter", "章节"),
        ("trusted_state_version", "可信版本"),
    ):
        value = metadata.get(key)
        if value is not None and str(value).strip():
            labels.append(f"{label}：{value}")
    return "；".join(labels)


def _audit_report_text(audit_report: dict[str, Any]) -> str:
    lines = ["AI 审核问题："]
    issues = audit_report.get("issues") if isinstance(audit_report, dict) else None
    unresolved = [
        issue for issue in issues or [] if isinstance(issue, dict) and not issue.get("resolved")
    ]
    if not unresolved:
        lines.append("- 无未解决审计问题。")
    for issue in unresolved:
        title = str(issue.get("title") or "未命名问题").strip()
        detail = str(
            issue.get("detail")
            or issue.get("description")
            or issue.get("message")
            or issue.get("suggested_fix")
            or ""
        ).strip()
        lines.append(f"- {title}" + (f"：{detail}" if detail else ""))
    suggestions = audit_report.get("suggestions") if isinstance(audit_report, dict) else None
    suggestion_lines = [str(item).strip() for item in suggestions or [] if str(item).strip()]
    if suggestion_lines:
        lines.append("AI 建议：")
        lines.extend(f"- {item}" for item in suggestion_lines)
    return "\n".join(lines)


def _revision_word_count_text(chapter: Chapter) -> str:
    target = parse_word_count(chapter.plan.get("word_budget"))
    if target is None:
        return ""
    current = len(chapter.draft_text or "")
    minimum = max(1, round(target * 0.9))
    maximum = max(minimum, round(target * 1.15))
    lines = [
        f"字数要求：目标 {target} 字，建议区间 {minimum}-{maximum} 字，当前约 {current} 字。",
        "不要用提纲、摘要、重复段落或冗余扩写凑字。",
    ]
    if current > maximum:
        lines.append("当前正文已经超出目标，请以删减和合并为主，不要新增支线、回忆或环境铺陈。")
    elif current < minimum:
        lines.append("当前正文低于目标，请只补必要的动作、因果和结尾钩子，不要重复已有信息。")
    else:
        lines.append("当前正文已在建议区间内，修订时尽量保持篇幅稳定。")
    return "\n".join(lines)


def _book_lines(book: dict[str, Any]) -> list[str]:
    lines = []
    for label, key in (
        ("书名", "title"),
        ("类型", "genre"),
        ("读者", "audience"),
        ("前提", "premise"),
    ):
        value = str(book.get(key) or "").strip()
        if value:
            lines.append(f"- {label}：{value}")
    return lines


def _entity_lines(
    title: str,
    items: object,
    fields: tuple[str, ...],
    limit: int,
) -> list[str]:
    if not isinstance(items, list) or not items:
        return []
    lines = [f"- {title}："]
    for item in items[:limit]:
        if not isinstance(item, dict):
            text = str(item).strip()
            if text:
                lines.append(f"  - {text}")
            continue
        values = [str(item.get(field) or "").strip() for field in fields]
        text = " / ".join(value for value in values if value)
        if text:
            lines.append(f"  - {text}")
    return lines if len(lines) > 1 else []


def _chapter_summary_lines(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return []
    lines = ["- 近期章节："]
    for item in items[-3:]:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("chapter") or "").strip()
            content = str(item.get("summary") or item.get("content") or "").strip()
            text = "：".join(part for part in (title, content) if part)
        else:
            text = str(item).strip()
        if text:
            lines.append(f"  - {text}")
    return lines if len(lines) > 1 else []


def _list_block(title: str, value: object) -> list[str]:
    if not isinstance(value, list) or not value:
        return []
    lines = [f"{title}："]
    lines.extend(f"- {str(item).strip()}" for item in value if str(item).strip())
    return lines


def _join_prompt_sections(sections: list[str]) -> str:
    return "\n\n".join(section for section in sections if section)
