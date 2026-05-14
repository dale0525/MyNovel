from __future__ import annotations

import html
import json
from copy import deepcopy
from typing import Any

from mynovel.domain.models import Canon, Chapter, ChapterStatus, RunTrace
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.product_components import render_accepted_result
from mynovel.word_targets import chapter_word_budget, format_word_count


def render_review_decision_summary(
    chapter: Chapter,
    canon: Canon | None,
    locale: str = DEFAULT_LOCALE,
    traces: list[RunTrace] | None = None,
) -> str:
    _ = canon
    return f"""
      <div class="review-summary-stack">
        {_render_completion_summary(chapter, locale)}
        {_render_state_change_summary(chapter, locale)}
        {_render_ai_fixed_summary(chapter, locale, traces or [])}
        {_render_remaining_decisions_summary(chapter, locale)}
      </div>
"""


def render_chapter_review_inspector(
    chapter: Chapter,
    canon: Canon | None,
    locale: str = DEFAULT_LOCALE,
    traces: list[RunTrace] | None = None,
) -> str:
    if chapter.status == ChapterStatus.PLANNED:
        return f"<h2>{t('review.waiting', locale)}</h2><p>{t('chapter.not_started', locale)}</p>"

    issues = _audit_issues(chapter)
    visible_changes = _visible_state_changes(chapter)
    major_changes = _major_state_changes(chapter)
    canon_version = canon.version if canon else 0
    risk_level = _risk_level(chapter.audit_report)

    return f"""
      <section class="review-inspector-head">
        <div>
          <p class="muted">人工审核关口</p>
          <h2>先确认风险，再决定是否写入可信设定</h2>
        </div>
        <span class="risk-badge {html.escape(risk_level)}">{_risk_label(risk_level)}</span>
      </section>
      {_render_review_tabs(len(issues), len(visible_changes), len(major_changes))}
      <div class="review-tab-panels">
        {_render_audit_panel(issues, locale)}
        {_render_state_panel(chapter, visible_changes, major_changes, canon_version, locale)}
        {_render_revision_panel(chapter)}
        {_render_impact_panel(visible_changes)}
      </div>
      {_render_repair_trace_panel(chapter, traces or [])}
      {_render_review_actions(chapter, major_changes, locale)}
      {_review_tab_script()}
"""


def _render_review_tabs(issue_count: int, change_count: int, major_count: int) -> str:
    return f"""
      <nav class="review-tabs interactive-tabs" aria-label="章节审核">
        {_tab_button("audit", "审计问题", str(issue_count), active=True)}
        {_tab_button("state", "状态变化", str(change_count))}
        {_tab_button("revision", "AI 修订", "正文")}
        {_tab_button("impact", "影响范围", str(major_count) if major_count else "检查")}
      </nav>
"""


def _tab_button(key: str, label: str, badge: str, *, active: bool = False) -> str:
    active_class = " active" if active else ""
    selected = "true" if active else "false"
    return (
        f'<button type="button" class="review-tab-button{active_class}" '
        f'data-review-tab="{key}" aria-selected="{selected}" '
        f'aria-controls="review-panel-{key}">'
        f"<span>{html.escape(label)}</span><em>{html.escape(badge)}</em></button>"
    )


def _render_audit_panel(issues: list[dict[str, Any]], locale: str) -> str:
    if issues:
        issue_rows = "".join(_issue_row(issue, locale) for issue in issues)
    else:
        issue_rows = """
          <li class="empty-review-row">
            <span>暂无未处理审计问题</span>
            <em>仍建议快速通读正文和状态变化</em>
          </li>
"""
    return f"""
      <section id="review-panel-audit" class="review-tab-panel active" data-review-panel="audit">
        <h2>{t("review.audit_issues", locale)}</h2>
        <p class="review-panel-copy">优先处理“仍需确认”的项目；已修复项仅作为复核线索。</p>
        <ul class="review-list structured-review-list">{issue_rows}</ul>
      </section>
"""


def _issue_row(issue: dict[str, Any], locale: str) -> str:
    resolved = bool(issue.get("resolved"))
    status = t("review.fixed", locale) if resolved else t("review.needs_confirm", locale)
    status_class = "fixed" if resolved else "needs-confirm"
    severity = _severity_label(issue.get("severity"))
    detail = issue.get("detail") or issue.get("description") or issue.get("message") or ""
    detail_html = f"<p>{html.escape(str(detail))}</p>" if detail else ""
    return f"""
      <li>
        <strong>{html.escape(str(issue.get("title") or "未命名审计问题"))}</strong>
        <span class="review-row-meta">
          <b>{html.escape(severity)}</b>
          <em class="{status_class}">{status}</em>
        </span>
        {detail_html}
      </li>
"""


def _render_state_panel(
    chapter: Chapter,
    changes: list[dict[str, Any]],
    major_changes: list[dict[str, Any]],
    canon_version: int,
    locale: str,
) -> str:
    if changes:
        delta_rows = "".join(_state_change_row(change) for change in changes)
    else:
        delta_rows = f"""
          <li class="empty-review-row">
            <span>{t("review.summary_state_empty", locale)}</span>
            <em>可以批准正文，但不要把空泛分类写入可信设定。</em>
          </li>
"""
    warning = (
        f"<p class='danger'>{t('review.major_change_count', locale, count=len(major_changes))}</p>"
        if major_changes
        else ""
    )
    return f"""
      <section id="review-panel-state" class="review-tab-panel" data-review-panel="state" hidden>
        <h2>{t("review.state_delta", locale)}</h2>
        <p class="review-panel-copy">当前可信设定版本：v{canon_version}。以下变化在批准后才会写入事实源。</p>
        {warning}
        <ul class="review-list structured-review-list state-change-list">{delta_rows}</ul>
        <details class="raw-state-delta">
          <summary>查看原始状态变化</summary>
          <pre>{html.escape(json.dumps(chapter.state_delta or {}, ensure_ascii=False, indent=2))}</pre>
        </details>
      </section>
"""


def _state_change_row(change: dict[str, Any]) -> str:
    change_type = _state_type_label(change.get("type"))
    target = str(change.get("target") or "待确认").strip()
    detail = str(change.get("change") or change.get("detail") or "").strip()
    risk = _severity_label(change.get("risk"))
    return f"""
      <li>
        <strong>{html.escape(change_type)} · {html.escape(target)}</strong>
        <span class="review-row-meta"><b>{html.escape(risk)}</b><em>待人工确认</em></span>
        <p>{html.escape(detail or "未提供明确变化内容")}</p>
      </li>
"""


def _render_revision_panel(chapter: Chapter) -> str:
    current_text = chapter.revised_text or chapter.draft_text or chapter.final_text
    source = "AI 修订稿" if chapter.revised_text else "草稿" if chapter.draft_text else "最终稿"
    excerpt = current_text[:180] + ("..." if len(current_text) > 180 else "")
    target_words = chapter_word_budget(chapter)
    minimum, maximum = _word_count_window(target_words)
    current_words = len(current_text)
    word_status = _word_count_status(current_words, minimum, maximum)
    return f"""
      <section id="review-panel-revision" class="review-tab-panel" data-review-panel="revision" hidden>
        <h2>AI 修订摘要</h2>
        <p class="review-panel-copy">当前正文来源：{html.escape(source)}。左侧阅读区显示完整正文，右侧仅保留审核线索。</p>
        <p class="review-panel-copy">目标区间 {minimum:,}-{maximum:,} 字，{html.escape(word_status)}。</p>
        <dl class="revision-metrics">
          <dt>目标字数</dt><dd>{html.escape(format_word_count(target_words))}</dd>
          <dt>草稿字数</dt><dd>{len(chapter.draft_text)}</dd>
          <dt>修订稿字数</dt><dd>{len(chapter.revised_text)}</dd>
          <dt>当前候选字数</dt><dd>{len(current_text)}</dd>
        </dl>
        <blockquote class="revision-excerpt">{html.escape(excerpt) if excerpt else "暂无正文候选。"}</blockquote>
      </section>
"""


def _render_impact_panel(changes: list[dict[str, Any]]) -> str:
    buckets: dict[str, list[str]] = {}
    for change in changes:
        bucket = _state_type_label(change.get("type"))
        buckets.setdefault(bucket, []).append(
            str(change.get("target") or change.get("change") or "待确认")
        )
    if not buckets:
        cards = """
          <section><strong>无明确影响范围</strong><p>本章没有可自动归类的可信设定变化。</p></section>
"""
    else:
        cards = "".join(
            f"<section><strong>{html.escape(key)} ({len(values)})</strong>"
            f"<p>{html.escape('、'.join(values[:3]))}</p></section>"
            for key, values in buckets.items()
        )
    return f"""
      <section id="review-panel-impact" class="review-tab-panel" data-review-panel="impact" hidden>
        <h2>影响范围</h2>
        <p class="review-panel-copy">用于判断这次批准会影响哪些设定分区。</p>
        <div class="impact-scope inline-impact-scope"><div>{cards}</div></div>
      </section>
"""


def _render_repair_trace_panel(chapter: Chapter, traces: list[RunTrace]) -> str:
    trace = _latest_repair_trace(chapter, traces)
    if trace is None:
        return ""

    metadata = trace.metadata_ or {}
    cost = trace.cost or {}
    before_words = _optional_int(metadata.get("before_word_count"))
    after_words = _optional_int(metadata.get("after_word_count"))
    target_words = _optional_int(metadata.get("target_word_count"))
    window = _word_count_window_text(metadata.get("word_count_window"))
    reviewer_note = str(metadata.get("reviewer_note") or "").strip()
    prompt_text = _prompt_messages_text(metadata.get("prompt_messages"))
    has_raw_response = bool(str(metadata.get("raw_response_text") or "").strip())
    legacy_patch_response = (
        not has_raw_response
        and bool(metadata.get("word_count_repair_mode"))
        and bool(metadata.get("patch_operations"))
    )
    raw_response_text = str(
        metadata.get("raw_response_text")
        or ("" if legacy_patch_response else metadata.get("response_text"))
        or ""
    ).strip()
    applied_text = str(
        metadata.get("applied_text")
        or (metadata.get("response_text") if legacy_patch_response else "")
        or ""
    ).strip()
    transition = _word_count_transition(before_words, after_words)
    target_line = (
        f"<span>目标 {target_words:,} 字 · 区间 {html.escape(window)}</span>"
        if target_words and window
        else ""
    )
    note_line = (
        f"<p class='review-panel-copy'>本次意见：{html.escape(reviewer_note)}</p>"
        if reviewer_note
        else ""
    )
    prompt_chars = _optional_int(cost.get("prompt_chars")) or 0
    completion_chars = _optional_int(cost.get("completion_chars")) or 0
    prompt_details = (
        f"<details><summary>查看提示词</summary><pre>{html.escape(prompt_text)}</pre></details>"
        if prompt_text
        else ""
    )
    response_details = (
        f"<details><summary>查看模型原始返回</summary><pre>{html.escape(raw_response_text)}</pre></details>"
        if raw_response_text
        else ""
    )
    applied_details = (
        f"<details><summary>{'查看旧版应用后正文' if legacy_patch_response else '查看应用后正文'}</summary>"
        f"<pre>{html.escape(applied_text)}</pre></details>"
        if applied_text and applied_text != raw_response_text
        else ""
    )

    return f"""
      <section class="repair-trace-panel">
        <h2>AI 修复记录</h2>
        <p class="review-panel-copy">最近一次修复：{html.escape(trace.model or "未记录模型")} · 提示词 {prompt_chars} 字符 · 模型返回 {completion_chars} 字符</p>
        <div class="repair-trace-metrics">
          <span>{html.escape(transition)}</span>
          {target_line}
        </div>
        {note_line}
        {prompt_details}
        {response_details}
        {applied_details}
      </section>
"""


def _render_review_actions(
    chapter: Chapter,
    major_changes: list[dict[str, Any]],
    locale: str,
) -> str:
    if chapter.status in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}:
        major_confirmation = ""
        if chapter.status == ChapterStatus.AWAITING_REVIEW and major_changes:
            major_confirmation = f"""
            <p class="danger">{t("review.major_change_warning", locale)}</p>
            <label class="inline-check"><input name="allow_major_changes" type="checkbox" value="1">{t("review.confirm_major_change", locale)}</label>
"""
        approve_form = ""
        if chapter.status == ChapterStatus.AWAITING_REVIEW:
            approve_form = f"""
          <form id="approve-form" method="post" action="/approve-chapter" class="compact-form action-form">
            <input type="hidden" name="chapter_id" value="{chapter.id}">
            {major_confirmation}
            <button type="submit">{t("action.accept_to_trusted_state", locale)}</button>
          </form>
"""
        return f"""
          <section class="review-decision-summary">
            <h2>{t("review.decision_note_title", locale)}</h2>
            <p>{t("review.decision_note_copy", locale)}</p>
          </section>
          <div class="review-action-stack review-decision-panel">
          <form method="post" action="/repair-chapter" class="compact-form action-form review-repair-form">
            <input type="hidden" name="chapter_id" value="{chapter.id}">
            <label>{t("review.decision_note_label", locale)}<textarea name="reviewer_note" placeholder="{html.escape(t('review.decision_note_placeholder', locale), quote=True)}"></textarea></label>
            <button class="secondary" type="submit">{t("review.decision_note_submit", locale)}</button>
          </form>
          {approve_form}
          </div>
"""
    if chapter.status == ChapterStatus.ACCEPTED:
        return f"""
          {render_accepted_result(chapter)}
          <div class="actions">
            <a class="button" href="/chapter/{chapter.id}/export">{t("action.export_chapter", locale)}</a>
          </div>
"""
    return ""


def _review_tab_script() -> str:
    return """
      <script>
        (() => {
          const root = document.currentScript.closest('.right-panel');
          if (!root) return;
          const buttons = root.querySelectorAll('[data-review-tab]');
          const panels = root.querySelectorAll('[data-review-panel]');
          buttons.forEach((button) => {
            button.addEventListener('click', () => {
              const key = button.dataset.reviewTab;
              buttons.forEach((item) => {
                const active = item === button;
                item.classList.toggle('active', active);
                item.setAttribute('aria-selected', active ? 'true' : 'false');
              });
              panels.forEach((panel) => {
                const active = panel.dataset.reviewPanel === key;
                panel.classList.toggle('active', active);
                panel.hidden = !active;
              });
            });
          });
        })();
      </script>
"""


def _audit_issues(chapter: Chapter) -> list[dict[str, Any]]:
    return [
        _display_audit_issue(chapter, issue)
        for issue in chapter.audit_report.get("issues", [])
        if isinstance(issue, dict)
    ]


def _display_audit_issue(chapter: Chapter, issue: dict[str, Any]) -> dict[str, Any]:
    display = deepcopy(issue)
    if display.get("resolved") or not _is_word_count_issue(display):
        return display

    current_text = chapter.revised_text or chapter.draft_text or chapter.final_text
    current_words = len(current_text)
    target_words = chapter_word_budget(chapter)
    minimum, maximum = _word_count_window(target_words)
    current_direction = _word_count_direction(current_words, minimum, maximum)
    if current_direction == "ok":
        return display

    issue_direction = _word_count_issue_direction(display)
    if issue_direction == current_direction and "自动复核" not in str(display.get("detail") or ""):
        return display

    display["title"] = "字数不在目标区间"
    display["detail"] = _word_count_recheck_detail(current_words, minimum, maximum, target_words)
    return display


def _visible_state_changes(chapter: Chapter) -> list[dict[str, Any]]:
    return [
        change
        for change in chapter.state_delta.get("changes", [])
        if isinstance(change, dict) and not _is_low_information_state_change(change)
    ]


def _is_low_information_state_change(change: dict[str, Any]) -> bool:
    target = str(change.get("target") or change.get("name") or "").strip()
    detail = str(change.get("change") or change.get("detail") or "").strip()
    if target != "待确认":
        return False
    return detail in {
        "人物",
        "关系",
        "地点",
        "资源",
        "伏笔",
        "信息暴露",
        "characters",
        "relationships",
        "relations",
        "locations",
        "resources",
        "foreshadowing",
        "information_exposure",
        "foreshadowing_and_info",
        "foreshadowing_and_information",
    }


def _major_state_changes(chapter: Chapter) -> list[dict[str, Any]]:
    return [
        change
        for change in chapter.state_delta.get("changes", [])
        if isinstance(change, dict) and _is_major_state_change(change)
    ]


def _is_major_state_change(change: dict[str, Any]) -> bool:
    impact = str(change.get("impact", "")).lower()
    if impact in {"major", "critical", "high"}:
        return True
    text = " ".join(str(change.get(key, "")) for key in ("type", "target", "change"))
    major_terms = ("角色死亡", "人物死亡", "死亡", "牺牲", "退场", "核心设定", "改写设定")
    return any(term in text for term in major_terms)


def _word_count_window(target_words: int) -> tuple[int, int]:
    minimum = max(1, round(target_words * 0.9))
    maximum = max(minimum, round(target_words * 1.15))
    return minimum, maximum


def _word_count_status(current_words: int, minimum: int, maximum: int) -> str:
    if current_words > maximum:
        return "当前偏长"
    if current_words < minimum:
        return "当前偏短"
    return "当前在目标区间内"


def _word_count_direction(current_words: int, minimum: int, maximum: int) -> str:
    if current_words > maximum:
        return "long"
    if current_words < minimum:
        return "short"
    return "ok"


def _word_count_recheck_detail(
    current_words: int,
    minimum: int,
    maximum: int,
    target_words: int,
) -> str:
    status = _word_count_status(current_words, minimum, maximum)
    return (
        f"页面实时复核：当前约 {current_words} 字，目标区间 {minimum:,}-{maximum:,} 字，"
        f"目标约 {target_words:,} 字；{status}。"
    )


def _is_word_count_issue(issue: dict[str, Any]) -> bool:
    text = " ".join(
        str(issue.get(key) or "")
        for key in ("title", "detail", "description", "message", "suggested_fix")
    )
    return any(term in text.lower() for term in ("字数", "篇幅", "达成率", "word count"))


def _word_count_issue_direction(issue: dict[str, Any]) -> str | None:
    text = " ".join(
        str(issue.get(key) or "")
        for key in ("title", "detail", "description", "message", "suggested_fix")
    ).lower()
    if any(term in text for term in ("删减", "压缩", "合并", "缩短", "超出", "过长", "偏长")):
        return "long"
    if any(
        term in text
        for term in (
            "扩写",
            "扩充",
            "增加",
            "补充",
            "加入更多",
            "更多",
            "拉长",
            "拉升",
            "远低于",
            "低于",
            "不足",
            "偏短",
            "未达标",
            "缺口",
            "达成度偏低",
            "达成率严重不足",
        )
    ):
        return "short"
    return None


def _latest_repair_trace(chapter: Chapter, traces: list[RunTrace]) -> RunTrace | None:
    for trace in reversed(traces):
        if trace.stage != "修复问题":
            continue
        trace_chapter = (trace.metadata_ or {}).get("chapter")
        if trace_chapter in {chapter.number, str(chapter.number), chapter.id, str(chapter.id)}:
            return trace
    return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _word_count_window_text(value: object) -> str:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return ""
    minimum = _optional_int(value[0])
    maximum = _optional_int(value[1])
    if minimum is None or maximum is None:
        return ""
    return f"{minimum:,}-{maximum:,} 字"


def _word_count_transition(before_words: int | None, after_words: int | None) -> str:
    if before_words is None or after_words is None:
        return "字数变化未记录"
    return f"{before_words:,} → {after_words:,}"


def _prompt_messages_text(value: object) -> str:
    if not isinstance(value, list):
        return ""
    lines: list[str] = []
    for message in value:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "message")
        content = str(message.get("content") or "").strip()
        if content:
            lines.append(f"[{role}]\n{content}")
    return "\n\n".join(lines)


def _risk_level(audit_report: dict[str, Any]) -> str:
    value = str(audit_report.get("risk_level") or "low").lower()
    if value in {"high", "medium", "low"}:
        return value
    return "low"


def _risk_label(level: str) -> str:
    return {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(level, "低风险")


def _severity_label(value: object) -> str:
    normalized = str(value or "").lower()
    if normalized in {"high", "高"}:
        return "高"
    if normalized in {"medium", "mid", "中"}:
        return "中"
    if normalized in {"low", "低"}:
        return "低"
    return "提示"


def _state_type_label(value: object) -> str:
    text = str(value or "状态变化").strip()
    labels = {
        "characters": "人物",
        "character": "人物",
        "relationships": "关系",
        "relations": "关系",
        "locations": "地点",
        "resources": "资源",
        "foreshadowing": "伏笔",
        "information_exposure": "信息暴露",
    }
    return labels.get(text, text)


def _render_completion_summary(chapter: Chapter, locale: str) -> str:
    summary = str(chapter.summary or "").strip() or t(
        "review.summary_completion_fallback",
        locale,
        number=chapter.number,
    )
    return (
        '<section class="review-summary-card">'
        f"<h2>{t('review.summary_completion_title', locale)}</h2>"
        f"<p>{html.escape(summary)}</p>"
        "</section>"
    )


def _render_state_change_summary(chapter: Chapter, locale: str) -> str:
    changes = _visible_state_changes(chapter)
    if not changes:
        return (
            '<section class="review-summary-card">'
            f"<h2>{t('review.summary_state_title', locale)}</h2>"
            f"<p>{t('review.summary_state_empty', locale)}</p>"
            "</section>"
        )
    rows = "".join(_state_change_summary_row(change) for change in changes[:5])
    return (
        '<section class="review-summary-card">'
        f"<h2>{t('review.summary_state_title', locale)}</h2>"
        f'<ul class="decision-question-list">{rows}</ul>'
        "</section>"
    )


def _state_change_summary_row(change: dict[str, Any]) -> str:
    label = _state_type_label(change.get("type"))
    target = str(change.get("target") or "").strip()
    detail = str(change.get("change") or change.get("detail") or "待人工确认").strip()
    target_prefix = f"{html.escape(target)}：" if target and target != "待确认" else ""
    return (
        "<li>"
        f'<span class="state-change-pill">{html.escape(label)}</span>'
        f"{target_prefix}{html.escape(detail)}"
        "</li>"
    )


def _render_ai_fixed_summary(
    chapter: Chapter,
    locale: str,
    traces: list[RunTrace],
) -> str:
    rows: list[str] = []
    for issue in _audit_issues(chapter):
        if issue.get("resolved"):
            rows.append(f"<li>{html.escape(str(issue.get('title') or '已处理问题'))}</li>")

    trace = _latest_repair_trace(chapter, traces)
    if trace is not None and not rows:
        reviewer_note = str((trace.metadata_ or {}).get("reviewer_note") or "").strip()
        if reviewer_note:
            rows.append(
                f"<li>{html.escape(t('review.summary_ai_fixed_trace', locale, note=reviewer_note))}</li>"
            )

    if not rows:
        return (
            '<section class="review-summary-card">'
            f"<h2>{t('review.summary_ai_fixed_title', locale)}</h2>"
            f"<p>{t('review.summary_ai_fixed_empty', locale)}</p>"
            "</section>"
        )
    return (
        '<section class="review-summary-card">'
        f"<h2>{t('review.summary_ai_fixed_title', locale)}</h2>"
        f'<ul class="decision-question-list">{"".join(rows)}</ul>'
        "</section>"
    )


def _render_remaining_decisions_summary(chapter: Chapter, locale: str) -> str:
    unresolved = _remaining_decision_items(chapter, locale)
    if not unresolved:
        body = f"<p>{t('review.summary_decisions_empty', locale)}</p>"
    else:
        items = "".join(f"<li>{item}</li>" for item in unresolved)
        body = f'<ul class="decision-question-list">{items}</ul>'
    return (
        '<section class="review-summary-card decision-questions">'
        f"<h2>{t('review.summary_decisions_title', locale)}</h2>"
        f"{body}"
        f"<p>{t('review.summary_decisions_hint', locale)}</p>"
        "</section>"
    )


def _remaining_decision_items(chapter: Chapter, locale: str) -> list[str]:
    items: list[str] = []
    for issue in _audit_issues(chapter):
        if issue.get("resolved"):
            continue
        title = str(issue.get("title") or "").strip()
        if title:
            items.append(html.escape(title))

    for change in _major_state_changes(chapter):
        target = str(change.get("target") or "").strip() or t("review.summary_state_pending", locale)
        detail = str(change.get("change") or change.get("detail") or "").strip()
        decision = t(
            "review.summary_major_decision",
            locale,
            target=target,
            detail=detail or t("review.summary_state_pending", locale),
        )
        items.append(html.escape(decision))

    return items[:5]
