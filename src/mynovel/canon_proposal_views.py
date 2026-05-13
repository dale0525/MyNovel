from __future__ import annotations

import html
from typing import Any

from mynovel.domain.models import Book, BookStatus, Canon, CanonProposalRevision
from mynovel.workflows.canon_proposal import (
    CANON_PROPOSAL_KEY,
    SECTION_REGISTRY,
    section_locks_for_book,
)


def render_canon_proposal_surface(
    book: Book,
    canon: Canon | None,
    locked: bool,
    revision: CanonProposalRevision | None = None,
) -> str:
    if canon is None:
        return "<p>还没有可信设定。</p>"

    content = canon.content
    locks = section_locks_for_book(book)
    editable = book.status == BookStatus.DRAFT and not locked
    warning = _render_status_warning(canon, locked)
    latest_revision = _render_latest_revision(book)
    preview = _render_revision_preview(book, revision, editable) if revision is not None else ""
    summaries = "".join(_render_summary_link(section.key, content.get(section.key)) for section in SECTION_REGISTRY.values())
    details = "".join(
        _render_section_detail(
            book=book,
            section_key=section.key,
            value=content.get(section.key, []),
            section_locked=locks.get(section.key, not section.editable),
            editable=editable and section.editable,
        )
        for section in SECTION_REGISTRY.values()
    )

    return f"""
      {warning}
      {latest_revision}
      {preview}
      <nav class="canon-summary-grid" aria-label="可信设定分区">
        {summaries}
      </nav>
      <section class="table-card chapter-production-basis"><h2>章节生产依据 · 前 10 章节奏</h2>{_render_chapter_rhythm(content)}</section>
      <div class="state-sections detail-state-sections">
        {details}
      </div>
"""


def _render_status_warning(canon: Canon, locked: bool) -> str:
    if locked:
        return (
            f'<div class="canon-warning">当前可信设定已锁定：版本 {canon.version} 是生产线事实源，'
            "只有通过审核的章节变化才能继续写入。</div>"
        )
    return '<div class="canon-warning">当前为草稿提案状态，只有锁定后，状态变化才会写入可信设定。</div>'


def _render_summary_link(section_key: str, value: Any) -> str:
    section = SECTION_REGISTRY[section_key]
    count = _section_count(value)
    summary = _section_summary(value)
    return (
        f'<a class="canon-summary-card" href="#{html.escape(section.anchor)}">'
        f"<h2>{html.escape(section.label)}</h2>"
        f"<strong>{count}</strong>"
        f"<p>{summary}</p>"
        '<b aria-hidden="true">›</b>'
        "</a>"
    )


def _render_section_detail(
    book: Book,
    section_key: str,
    value: Any,
    section_locked: bool,
    editable: bool,
) -> str:
    section = SECTION_REGISTRY[section_key]
    controls = _render_section_controls(book, section_key, section_locked, editable)
    revision_form = ""
    if editable and not section_locked:
        revision_form = _render_revision_form(book, section_key)
    elif section.editable and section_locked:
        revision_form = '<p class="muted">此部分已锁定，AI 修订不会改写这里。</p>'

    return f"""
        <section id="{html.escape(section.anchor)}" class="data-card canon-section-panel">
          <header class="canon-section-head">
            <div>
              <h2>{html.escape(section.label)}</h2>
              <p>{_section_summary(value)}</p>
            </div>
            {controls}
          </header>
          {_render_full_value(value)}
          {revision_form}
        </section>
"""


def _render_section_controls(book: Book, section_key: str, section_locked: bool, editable: bool) -> str:
    section = SECTION_REGISTRY[section_key]
    state = "已锁定" if section_locked else "可修订"
    if not editable:
        return f'<span class="status-pill {"trusted" if section_locked else "pending"}">{state}</span>'

    next_locked = "false" if section_locked else "true"
    action = "解除锁定" if section_locked else "锁定此部分"
    return f"""
      <form class="inline-form canon-section-lock" method="post" action="/canon-proposal-lock">
        <input type="hidden" name="book_id" value="{book.id or 0}">
        <input type="hidden" name="section" value="{html.escape(section.key)}">
        <input type="hidden" name="locked" value="{next_locked}">
        <span class="status-pill {"trusted" if section_locked else "pending"}">{state}</span>
        <button class="button secondary compact-button" type="submit">{action}</button>
      </form>
"""


def _render_revision_form(book: Book, section_key: str) -> str:
    return f"""
      <form class="canon-revision-form" method="post" action="/canon-proposal-revise">
        <input type="hidden" name="book_id" value="{book.id or 0}">
        <input type="hidden" name="target_section" value="{html.escape(section_key)}">
        <label>
          <span>让 AI 修改这部分</span>
          <textarea name="instruction" rows="3" placeholder="说明要调整的事实、边界或人物设定" required></textarea>
        </label>
        <button type="submit">生成修订预览</button>
      </form>
"""


def _render_latest_revision(book: Book) -> str:
    proposal = book.constraints.get(CANON_PROPOSAL_KEY, {})
    if not isinstance(proposal, dict):
        return ""
    revision = proposal.get("last_revision")
    if not isinstance(revision, dict):
        return ""
    section = SECTION_REGISTRY.get(str(revision.get("target_section") or ""))
    section_label = section.label if section is not None else "未指定分区"
    summary = html.escape(str(revision.get("summary") or "暂无摘要"))
    return f"""
      <section class="canon-latest-revision">
        <h2>最近一次 AI 修订</h2>
        <p><strong>{html.escape(section_label)}</strong> · {summary}</p>
      </section>
"""


def _render_revision_preview(
    book: Book,
    revision: CanonProposalRevision,
    editable: bool,
) -> str:
    changed = "".join(
        _render_changed_section(section_key, value)
        for section_key, value in (revision.changed_sections or {}).items()
    )
    blocked = _render_blocked_sections(revision.blocked_sections or [])
    risks = _render_risks(revision.risks or [])
    regenerate = _render_regenerate_form(book, revision) if editable else ""
    actions = ""
    readonly_note = ""
    if editable:
        actions = f"""
        <div class="canon-preview-actions">
          {_revision_action_form(book, revision, "/canon-proposal-apply", "应用修订")}
          {_revision_action_form(book, revision, "/canon-proposal-discard", "放弃修订")}
        </div>
"""
    else:
        readonly_note = '<p class="muted">当前可信设定已锁定，此修订预览仅可查看。</p>'
    return f"""
      <section class="canon-revision-preview">
        <header>
          <h2>修订预览</h2>
          <p>{html.escape(revision.summary or "等待确认后应用到可信设定提案。")}</p>
        </header>
        {actions}
        {readonly_note}
        {changed}
        {blocked}
        {risks}
        {regenerate}
      </section>
"""


def _render_changed_section(section_key: str, value: Any) -> str:
    section = SECTION_REGISTRY.get(section_key)
    label = section.label if section is not None else section_key
    return f"""
        <section class="canon-preview-section">
          <h3>{html.escape(label)}</h3>
          {_render_full_value(value)}
        </section>
"""


def _render_blocked_sections(blocked_sections: list[Any]) -> str:
    if not blocked_sections:
        return ""
    items = []
    for item in blocked_sections:
        if isinstance(item, dict):
            section = SECTION_REGISTRY.get(str(item.get("section") or ""))
            label = section.label if section is not None else str(item.get("section") or "未知分区")
            reason = str(item.get("reason") or "已锁定")
            items.append(f"<li><strong>{html.escape(label)}</strong>：{html.escape(reason)}</li>")
        else:
            items.append(f"<li>{html.escape(str(item))}</li>")
    return "<section class=\"canon-preview-section\"><h3>未修改分区</h3><ul>" + "".join(items) + "</ul></section>"


def _render_risks(risks: list[Any]) -> str:
    if not risks:
        return ""
    return (
        '<section class="canon-preview-section"><h3>风险提示</h3><ul>'
        + "".join(f"<li>{html.escape(str(risk))}</li>" for risk in risks)
        + "</ul></section>"
    )


def _revision_action_form(
    book: Book,
    revision: CanonProposalRevision,
    action: str,
    label: str,
) -> str:
    return f"""
      <form class="inline-form" method="post" action="{action}">
        <input type="hidden" name="book_id" value="{book.id or 0}">
        <input type="hidden" name="revision_id" value="{revision.id or 0}">
        <button type="submit">{label}</button>
      </form>
"""


def _render_regenerate_form(book: Book, revision: CanonProposalRevision) -> str:
    return f"""
      <form class="canon-revision-form" method="post" action="/canon-proposal-revise">
        <input type="hidden" name="book_id" value="{book.id or 0}">
        <input type="hidden" name="target_section" value="{html.escape(revision.target_section)}">
        <label>
          <span>重新生成</span>
          <textarea name="instruction" rows="3" required>{html.escape(revision.instruction)}</textarea>
        </label>
        <button type="submit">重新生成预览</button>
      </form>
"""


def _section_count(value: Any) -> str:
    if isinstance(value, list):
        return f"{len(value)} 条"
    if isinstance(value, dict):
        return f"{len(value)} 项"
    if value:
        return "1 项"
    return "0 条"


def _section_summary(value: Any) -> str:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            text = first.get("name") or first.get("title") or first.get("summary") or first.get("detail")
            if text:
                return html.escape(_truncate(str(text)))
        return html.escape(_truncate(str(first)))
    if isinstance(value, dict) and value:
        return html.escape(_truncate(", ".join(str(key) for key in value.keys())))
    return "暂无内容"


def _render_chapter_rhythm(content: dict[str, Any]) -> str:
    chapters = content.get("chapter_summaries") or content.get("chapter_directions") or []
    if not isinstance(chapters, list) or not chapters:
        chapters = [
            {"chapter": index, "title": f"第 {index:02d} 章", "summary": "阶段性推进与新目标"}
            for index in range(1, 11)
        ]
    rows = []
    for index, chapter in enumerate(chapters[:10], start=1):
        if isinstance(chapter, dict):
            title = chapter.get("title") or chapter.get("chapter") or f"第 {index:02d} 章"
            goal = (
                chapter.get("summary")
                or chapter.get("direction")
                or chapter.get("goal")
                or "推进承诺"
            )
        else:
            title = f"第 {index:02d} 章"
            goal = str(chapter)
        rows.append(
            f"<tr><td>{index:02d}</td><td>{html.escape(str(title))}</td><td>{html.escape(str(goal))}</td></tr>"
        )
    return "<table><tbody>" + "".join(rows) + "</tbody></table>"


def _render_full_value(value: Any) -> str:
    if isinstance(value, list):
        visible_items = [item for item in value if not _is_low_information_state_item(item)]
        if not visible_items:
            return "<p class=\"muted\">暂无内容</p>"
        return "<ul class=\"value-list\">" + "".join(
            f"<li>{_render_full_value(item)}</li>" for item in visible_items
        ) + "</ul>"
    if isinstance(value, dict):
        concise = _unknown_target_detail(value)
        if concise:
            return f"<p>{html.escape(concise)}</p>"
        if not value:
            return "<p class=\"muted\">暂无内容</p>"
        visible_items = (
            (key, item) for key, item in value.items() if not _is_internal_state_key(key)
        )
        parts = [
            f"{_label_key(key)}：{_render_inline_value(item)}"
            for key, item in visible_items
        ]
        return "<p>" + "；".join(parts) + "</p>"
    if value in (None, ""):
        return "<p class=\"muted\">暂无内容</p>"
    return f"<p>{html.escape(str(value))}</p>"


def _label_key(key: object) -> str:
    labels = {
        "chapter": "章节",
        "change": "内容",
        "changes": "变化",
        "detail": "内容",
        "direction": "方向",
        "from": "起点",
        "goal": "目标",
        "identity": "身份",
        "impact": "影响",
        "mechanism": "机制",
        "motivation": "动机",
        "name": "名称",
        "personality": "性格",
        "role": "定位",
        "rules": "规则",
        "setting": "背景",
        "summary": "摘要",
        "target": "对象",
        "title": "标题",
        "to": "终点",
        "trait": "特质",
        "type": "类型",
    }
    return html.escape(labels.get(str(key), str(key)))


def _render_inline_value(value: Any) -> str:
    if isinstance(value, dict):
        concise = _unknown_target_detail(value)
        if concise:
            return html.escape(concise)
        return "；".join(
            f"{_label_key(key)}：{_render_inline_value(item)}"
            for key, item in value.items()
            if not _is_internal_state_key(key)
        )
    if isinstance(value, list):
        return "、".join(
            _render_inline_value(item)
            for item in value
            if not _is_low_information_state_item(item)
        )
    return html.escape(str(value))


def _is_internal_state_key(key: object) -> bool:
    return str(key) in {"chapter_title", "updated_at", "accepted_at"}


def _is_low_information_state_item(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if str(value.get("name") or value.get("target") or "").strip() != "待确认":
        return False
    detail = str(value.get("detail") or value.get("change") or "").strip()
    return detail in _LOW_INFORMATION_VALUES


def _unknown_target_detail(value: dict) -> str:
    if str(value.get("name") or value.get("target") or "").strip() != "待确认":
        return ""
    detail = str(value.get("detail") or value.get("change") or "").strip()
    if detail in _LOW_INFORMATION_VALUES:
        return ""
    return detail


_LOW_INFORMATION_VALUES = {
    "人物",
    "关系",
    "地点",
    "资源",
    "伏笔",
    "信息暴露",
    "characters",
    "relationships",
    "locations",
    "resources",
    "foreshadowing",
    "information_exposure",
    "foreshadowing_and_info",
    "foreshadowing_and_information",
}


def _truncate(text: str, limit: int = 64) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
