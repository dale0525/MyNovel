from __future__ import annotations

import html
from typing import Any

from mynovel.domain.models import (
    Book,
    BookStatus,
    Canon,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
)
from mynovel.workflows.canon_proposal import (
    CANON_PROPOSAL_KEY,
    CANON_PROPOSAL_COMPLETION_INSTRUCTION,
    SECTION_REGISTRY,
    canon_proposal_completion_target,
    canon_proposal_readiness,
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
    readiness = canon_proposal_readiness(content)
    allow_section_edits = editable and readiness.complete
    warning = _render_status_warning(canon, locked)
    completion_gate = (
        ""
        if revision is not None
        else _render_completion_gate(book, content, locks, editable, locked)
    )
    latest_revision = _render_latest_revision(book)
    preview = _render_revision_preview(book, revision, editable) if revision is not None else ""
    summaries = "".join(
        _render_summary_link(section.key, content.get(section.key), readiness.missing_sections)
        for section in SECTION_REGISTRY.values()
    )
    details = "".join(
        _render_section_detail(
            book=book,
            section_key=section.key,
            value=content.get(section.key, []),
            section_locked=locks.get(section.key, not section.editable),
            editable=allow_section_edits and section.editable,
        )
        for section in SECTION_REGISTRY.values()
    )

    return f"""
      {warning}
      {completion_gate}
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


def _render_completion_gate(
    book: Book,
    content: dict[str, Any],
    locks: dict[str, bool],
    editable: bool,
    locked: bool,
) -> str:
    if locked:
        return ""
    readiness = canon_proposal_readiness(content)
    if readiness.complete:
        return """
      <section class="canon-completion-gate trusted">
        <h2>定盘信息已达到可锁定标准</h2>
        <p>可以继续细看各分区；如果方向没有问题，就在右侧锁定并开始生产。</p>
      </section>
"""

    missing = "".join(f"<li>{html.escape(message)}</li>" for message in readiness.messages)
    target_section = canon_proposal_completion_target(content, locks)
    action = ""
    if editable and target_section is not None:
        action = f"""
        <form method="post" action="/canon-proposal-revise" class="canon-completion-form">
          <input type="hidden" name="book_id" value="{book.id or 0}">
          <input type="hidden" name="target_section" value="{html.escape(target_section)}">
          <input type="hidden" name="instruction" value="{html.escape(CANON_PROPOSAL_COMPLETION_INSTRUCTION, quote=True)}">
          <button type="submit">让 AI 补全定盘</button>
        </form>
"""
    elif editable:
        action = '<p class="muted">缺失分区都已锁定，需要先解除对应分区锁定。</p>'

    return f"""
      <section id="canon-completion" class="canon-completion-gate">
        <div>
          <h2>定盘信息不足</h2>
          <p>当前内容还只是开书方向草稿，直接锁定会让后续章节缺少人物、势力、地点和关系依据。</p>
        </div>
        <ul>{missing}</ul>
        {action}
      </section>
"""


def _render_summary_link(section_key: str, value: Any, missing_sections: list[str]) -> str:
    section = SECTION_REGISTRY[section_key]
    count = _section_count(value)
    summary = _section_summary(value)
    missing_class = " missing" if section_key in missing_sections else ""
    return (
        f'<a class="canon-summary-card{missing_class}" href="#{html.escape(section.anchor)}">'
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
              <p>{_section_detail_summary(section_key, value)}</p>
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
      <details class="canon-revision-details">
        <summary>需要调整此部分</summary>
      <form class="canon-revision-form" method="post" action="/canon-proposal-revise">
        <input type="hidden" name="book_id" value="{book.id or 0}">
        <input type="hidden" name="target_section" value="{html.escape(section_key)}">
        <label>
          <span>让 AI 修改这部分</span>
          <textarea name="instruction" rows="3" placeholder="说明要调整的事实、边界或人物设定" required></textarea>
        </label>
        <button type="submit">生成修订预览</button>
      </form>
      </details>
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
    if revision.status == CanonProposalRevisionStatus.RUNNING:
        return _render_revision_running(revision)
    if revision.status == CanonProposalRevisionStatus.FAILED:
        return _render_revision_failed(book, revision, editable)

    changed_sections = revision.changed_sections or {}
    changed = "".join(
        _render_changed_section(section_key, value)
        for section_key, value in changed_sections.items()
    )
    blocked = _render_blocked_sections(revision.blocked_sections or [])
    risks = _render_risks(revision.risks or [])
    regenerate = _render_regenerate_form(book, revision) if editable else ""
    actions = ""
    readonly_note = ""
    if editable:
        actions = f"""
        <div class="canon-preview-actions">
          {_revision_action_form(book, revision, "/canon-proposal-apply", "应用到定盘提案")}
          {_revision_action_form(book, revision, "/canon-proposal-discard", "放弃这次预览", secondary=True)}
        </div>
"""
    else:
        readonly_note = '<p class="muted">当前可信设定已锁定，此修订预览仅可查看。</p>'
    return f"""
      <section id="canon-revision-job" class="canon-revision-preview">
        <header class="canon-preview-head">
          <div>
            <h2>AI 已生成定盘补全预览</h2>
            <p><strong>修订预览 · 待确认</strong> · 尚未写入可信设定提案，应用后才会替换下方分区。</p>
            <p>{html.escape(revision.summary or "等待确认后应用到可信设定提案。")}</p>
          </div>
          <span class="status-pill pending">待确认</span>
        </header>
        {_render_revision_impact_summary(changed_sections, revision)}
        {actions}
        {readonly_note}
        <div class="canon-preview-sections">{changed}</div>
        {blocked}
        {risks}
        {regenerate}
      </section>
"""


def _render_revision_running(revision: CanonProposalRevision) -> str:
    href = f"/book/{revision.book_id}/state?revision_id={revision.id or 0}#canon-revision-job"
    target = SECTION_REGISTRY.get(revision.target_section)
    target_label = target.label if target is not None else "定盘"
    return f"""
      <section id="canon-revision-job" class="canon-revision-preview canon-revision-job">
        <header>
          <div>
            <h2>AI 正在补全定盘</h2>
            <p>正在围绕「{html.escape(target_label)}」生成可审核的修订预览，完成后会自动显示可应用内容。</p>
          </div>
          <span class="status-pill pending">自动刷新中</span>
        </header>
        <div class="blueprint-generating-timeline">
          <article class="done"><span>✓</span><div><strong>修改意见已收到</strong><p>{html.escape(revision.instruction)}</p></div></article>
          <article class="current"><span>●</span><div><strong>模型正在修订</strong><p>只会改写未锁定分区，并保留锁定部分。</p></div><b class="loading-wave" aria-hidden="true">••••••••••••••</b></article>
          <article><span>○</span><div><strong>生成修订预览</strong><p>完成后由作者确认是否应用。</p></div></article>
        </div>
        <script>setTimeout(() => window.location.reload(), 3000)</script>
        <p><a class="button secondary" href="{href}">立即刷新</a></p>
      </section>
"""


def _render_revision_failed(
    book: Book,
    revision: CanonProposalRevision,
    editable: bool,
) -> str:
    regenerate = _render_regenerate_form(book, revision) if editable else ""
    risks = _render_risks(revision.risks or ["请稍后重试，或缩小修改范围。"])
    return f"""
      <section id="canon-revision-job" class="canon-revision-preview">
        <header>
          <h2>AI 修订生成失败</h2>
          <p>{html.escape(revision.summary or "模型没有返回可用的修订预览。")}</p>
        </header>
        {risks}
        {regenerate}
      </section>
"""


def _render_changed_section(section_key: str, value: Any) -> str:
    section = SECTION_REGISTRY.get(section_key)
    label = section.label if section is not None else section_key
    return f"""
        <section class="canon-preview-section">
          <header>
            <h3>{html.escape(label)}</h3>
            <span>{_section_count(value)}</span>
          </header>
          {_render_preview_section_value(section_key, value)}
        </section>
"""


def _render_revision_impact_summary(
    changed_sections: dict[str, Any],
    revision: CanonProposalRevision,
) -> str:
    labels = []
    for section_key in changed_sections:
        section = SECTION_REGISTRY.get(section_key)
        labels.append(section.label if section is not None else section_key)
    changed = "、".join(labels) if labels else "暂无分区"
    locked_count = len(revision.locked_sections or [])
    risk_count = len(revision.risks or [])
    return f"""
        <div class="canon-preview-summary" aria-label="修订影响范围">
          <span><strong>本次将更新</strong><em>{html.escape(changed)}</em></span>
          <span><strong>锁定分区</strong><em>{locked_count} 个不会改写</em></span>
          <span><strong>风险提示</strong><em>{risk_count} 条</em></span>
        </div>
"""


def _render_preview_section_value(section_key: str, value: Any) -> str:
    if section_key == "chapter_summaries":
        return _render_chapter_summary_preview(value)
    return _render_full_value(value)


def _render_chapter_summary_preview(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "<p class=\"muted\">暂无内容</p>"
    items = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            items.append(f"<li><p>{html.escape(str(item))}</p></li>")
            continue
        title = str(item.get("title") or item.get("chapter") or f"第 {index:02d} 章").strip()
        summary = str(
            item.get("summary")
            or item.get("content")
            or item.get("direction")
            or item.get("goal")
            or item.get("detail")
            or ""
        ).strip()
        chapter = item.get("chapter")
        prefix = f"第 {chapter} 章" if chapter and str(chapter) not in title else ""
        heading = " · ".join(part for part in (prefix, title) if part)
        body = f"<p>{html.escape(summary)}</p>" if summary else ""
        items.append(f"<li><strong>{html.escape(heading)}</strong>{body}</li>")
    return '<ul class="chapter-preview-list">' + "".join(items) + "</ul>"


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
    *,
    secondary: bool = False,
) -> str:
    button_class = ' class="secondary"' if secondary else ""
    return f"""
      <form class="inline-form" method="post" action="{action}">
        <input type="hidden" name="book_id" value="{book.id or 0}">
        <input type="hidden" name="revision_id" value="{revision.id or 0}">
        <button{button_class} type="submit">{label}</button>
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
            foreshadowing = _foreshadowing_text(first)
            if foreshadowing:
                return html.escape(_truncate(foreshadowing, 120))
            relationship = _relationship_text(first)
            if relationship:
                return html.escape(_truncate(relationship, 120))
            text = first.get("name") or first.get("title") or first.get("summary") or first.get("detail")
            if text:
                return html.escape(_truncate(str(text)))
            return _truncate(_render_inline_value(first), 120)
        return html.escape(_truncate(str(first)))
    if isinstance(value, dict) and value:
        return html.escape(_truncate(", ".join(str(key) for key in value.keys())))
    return "暂无内容"


def _section_detail_summary(section_key: str, value: Any) -> str:
    if section_key == "relationships":
        count = _visible_list_count(value)
        if count:
            return f"共 {count} 条人物关系，见下方列表。"
    if section_key == "foreshadowing":
        count = _visible_list_count(value)
        if count:
            return f"共 {count} 条伏笔，见下方列表。"
    return _section_summary(value)


def _visible_list_count(value: Any) -> int:
    if not isinstance(value, list):
        return 0
    return len([item for item in value if not _is_low_information_state_item(item)])


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
        history = _state_history_text(value)
        if history:
            return f"<p>{html.escape(history)}</p>"
        foreshadowing = _foreshadowing_text(value)
        if foreshadowing:
            return f"<p>{html.escape(foreshadowing)}</p>"
        relationship = _relationship_text(value)
        if relationship:
            return f"<p>{html.escape(relationship)}</p>"
        concise = _unknown_target_detail(value)
        if concise:
            return f"<p>{html.escape(concise)}</p>"
        if not value:
            return "<p class=\"muted\">暂无内容</p>"
        dict_items = (
            (key, item) for key, item in value.items() if not _is_internal_state_key(key)
        )
        parts = [
            f"{_label_key(key)}：{_render_inline_value(item)}"
            for key, item in dict_items
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
        "background": "背景",
        "content": "摘要",
        "description": "说明",
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
        "premise": "前提",
        "role": "定位",
        "rules": "规则",
        "setting": "背景",
        "skills": "技能",
        "summary": "摘要",
        "target": "对象",
        "title": "标题",
        "to": "终点",
        "trait": "特质",
        "trigger": "触发",
        "type": "类型",
    }
    return html.escape(labels.get(str(key), str(key)))


def _render_inline_value(value: Any) -> str:
    if isinstance(value, dict):
        history = _state_history_text(value)
        if history:
            return html.escape(history)
        foreshadowing = _foreshadowing_text(value)
        if foreshadowing:
            return html.escape(foreshadowing)
        relationship = _relationship_text(value)
        if relationship:
            return html.escape(relationship)
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


def _state_history_text(value: dict[str, Any]) -> str:
    if value.get("type") != "canon_proposal_revision":
        return ""
    target = _section_label(value.get("target_section")) or "未指定分区"
    parts = [f"AI 定盘修订：{target}"]
    changed = _section_labels(value.get("changed_sections"))
    if changed:
        parts.append(f"更新分区：{changed}")
    blocked = _blocked_section_labels(value.get("blocked_sections"))
    if blocked:
        parts.append(f"锁定未改：{blocked}")
    summary = str(value.get("summary") or "").strip()
    if summary:
        parts.append(f"摘要：{summary}")
    instruction = str(value.get("instruction") or "").strip()
    if instruction:
        parts.append(f"说明：{instruction}")
    risks = _history_list_text(value.get("risks"))
    if risks:
        parts.append(f"风险：{risks}")
    return "；".join(parts)


def _section_label(value: Any) -> str:
    section = SECTION_REGISTRY.get(str(value or ""))
    return section.label if section is not None else ""


def _section_labels(value: Any) -> str:
    if isinstance(value, dict):
        keys = list(value.keys())
    elif isinstance(value, list):
        keys = value
    else:
        keys = []
    labels = [_section_label(key) or str(key) for key in keys if str(key).strip()]
    return "、".join(labels)


def _blocked_section_labels(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    labels = []
    for item in value:
        if isinstance(item, dict):
            section = _section_label(item.get("section")) or str(item.get("section") or "未知分区")
            reason = str(item.get("reason") or "已锁定").strip()
            labels.append(f"{section}（{reason}）")
        elif str(item).strip():
            labels.append(str(item).strip())
    return "、".join(labels)


def _history_list_text(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    return "、".join(str(item).strip() for item in value if str(item).strip())


def _foreshadowing_text(value: dict[str, Any]) -> str:
    trigger = str(value.get("trigger") or "").strip()
    if not trigger:
        return ""
    description = str(
        value.get("description")
        or value.get("detail")
        or value.get("content")
        or value.get("summary")
        or ""
    ).strip()
    return f"{trigger}：{description}" if description else trigger


def _relationship_text(value: dict[str, Any]) -> str:
    actors = _relationship_actors(value)
    relation = str(value.get("relation") or "").strip()
    detail = str(
        value.get("detail")
        or value.get("description")
        or value.get("content")
        or value.get("summary")
        or ""
    ).strip()
    if not actors and not relation:
        return ""
    if actors and relation:
        head = f"{actors}：{relation}"
    else:
        head = actors or relation
    if detail:
        return f"{head}。{detail}" if head else detail
    return head


def _relationship_actors(value: dict[str, Any]) -> str:
    subjects = value.get("subjects")
    if isinstance(subjects, list):
        return "、".join(str(item).strip() for item in subjects if str(item).strip())
    if isinstance(subjects, str) and subjects.strip():
        return subjects.strip()
    start = str(value.get("from") or "").strip()
    end = str(value.get("to") or "").strip()
    if start and end:
        return f"{start} → {end}"
    return start or end


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
