from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from mynovel.blueprint_review_views import render_blueprint_review
from mynovel.blueprint_views import render_blueprint_sidebar, render_generating_blueprint
from mynovel.canon_proposal_views import render_canon_proposal_surface
from mynovel.chapter_review_views import render_chapter_review_inspector
from mynovel.domain.models import (
    Book,
    BookStatus,
    BlueprintStatus,
    Canon,
    Chapter,
    ChapterStatus,
    CanonProposalRevision,
    OpenBookBlueprint,
    ProviderConfig,
    RunTrace,
    VolumePlan,
)
from mynovel.home_views import render_empty_home, render_project_home
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.open_book_views import (
    render_open_book_focus_panel,
    render_open_book_optional_fields,
    render_open_book_preview_sidebar,
)
from mynovel.product_components import (
    render_canon_gate_aside,
    render_chapter_production_main,
    render_completed_aside,
    render_completed_progress,
    render_model_setup_content,
)
from mynovel.ui_shell import PipelineStep, render_app_page, render_pipeline, render_project_sidebar
from mynovel.ui_status_views import render_global_status_strip
from mynovel.word_target_views import render_word_target_form
from mynovel.word_targets import DEFAULT_CHAPTER_WORD_COUNT, DEFAULT_TARGET_WORD_COUNT

GENRE_PRESETS = (
    "玄幻升级",
    "都市异能",
    "悬疑推理",
    "科幻冒险",
    "古言权谋",
    "现言情感",
    "无限流",
    "轻小说",
)

AUDIENCE_PRESETS = (
    "男频网文读者",
    "女频网文读者",
    "悬疑推理读者",
    "轻小说读者",
    "成长冒险读者",
    "短篇精品读者",
)


def render_home(
    db_path: Path,
    books: list[Book],
    provider_config: ProviderConfig | None,
    blueprints: list[OpenBookBlueprint] | None = None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    blueprints = blueprints or []
    configured = is_provider_config_complete(provider_config)
    if books:
        main = render_project_home(books, blueprints, configured, locale)
        content_class = "content-grid home-focus-layout"
        bottom = _render_start_pipeline(None, locale)
    else:
        main = render_empty_home(provider_config, blueprints, configured, locale)
        content_class = "content-grid first-launch-layout"
        bottom = _render_first_launch_pipeline(locale)
    return _page(
        title=t("app.title", locale),
        active="workspace",
        main=main,
        message=message,
        bottom=bottom,
        locale=locale,
        db_path=db_path,
        content_class=content_class,
        nav_book_id=books[0].id if books else None,
        status_strip=render_global_status_strip(locale),
    )


def render_model_setup_page(
    db_path: Path,
    provider_config: ProviderConfig | None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    return _page(
        title=t("model.title", locale),
        active="create",
        main=render_model_setup_content(db_path, provider_config, locale),
        message=message,
        bottom=_render_start_pipeline(None, locale),
        locale=locale,
        db_path=db_path,
        eyebrow=t("model.title", locale),
        content_class="content-grid model-setup-layout",
    )


def render_new_book_page(
    provider_config: ProviderConfig | None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    disabled = "" if is_provider_config_complete(provider_config) else " disabled"
    form = f"""
      <form method="post" action="/open-book" class="single-focus-form">
        <label class="idea-field">{t("new_book.focus_title", locale)}
          <textarea name="idea" placeholder="{t("book.idea_placeholder", locale)}" required></textarea>
        </label>
        {render_open_book_optional_fields(
            genre_options=GENRE_PRESETS,
            audience_options=AUDIENCE_PRESETS,
            default_target_words=DEFAULT_TARGET_WORD_COUNT,
            default_chapter_words=DEFAULT_CHAPTER_WORD_COUNT,
            locale=locale,
        )}
        <div class="actions">
          <a class="button secondary" href="/">{t("action.back", locale)}</a>
          <button type="submit"{disabled}>{t("new_book.generate", locale)}</button>
        </div>
      </form>
"""
    main = f"""
      <aside class="side-panel book-wizard step-rail">
        <h2>{t("new_book.title", locale)}</h2>
        <p>{t("new_book.subtitle", locale)}</p>
        <ol class="step-list vertical-flow">
          <li class="active"><strong>{t("new_book.step_settings", locale)}</strong><span>只先完成这一步</span></li>
          <li><strong>{t("new_book.step_proposal", locale)}</strong><span>比较生成方案后再决定</span></li>
          <li><strong>{t("new_book.step_foundation", locale)}</strong><span>定盘后再开始章节生产</span></li>
        </ol>
        <p class="hint-box">先完成这一项，系统再把开书方案整理给你确认。</p>
      </aside>
      {render_open_book_focus_panel(form, locale)}
      {render_open_book_preview_sidebar(locale)}
"""
    return _page(
        title=t("new_book.title", locale),
        active="create",
        main=main,
        message=message,
        bottom=_render_start_pipeline("open_book", locale),
        locale=locale,
        content_class="content-grid book-creation-layout",
    )


def render_blueprint_page(
    db_path: Path,
    provider_config: ProviderConfig | None,
    blueprint: OpenBookBlueprint,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    _ = db_path
    content = blueprint.content or {}
    status_label = blueprint_status_label(blueprint.status, locale)
    if blueprint.status in {BlueprintStatus.PENDING, BlueprintStatus.RUNNING}:
        model_name = provider_config.llm_model if provider_config else None
        body = render_generating_blueprint(blueprint, locale, model_name)
    elif blueprint.status == BlueprintStatus.FAILED:
        body = f"""
          <section class="main-panel single">
            <h1>{t("blueprint.failed", locale)}</h1>
            <p class="danger">{html.escape(blueprint.error_message or blueprint.parse_error or "")}</p>
            <form method="post" action="/retry-blueprint" class="actions">
              <input type="hidden" name="blueprint_id" value="{blueprint.id}">
              <button type="submit">{t("blueprint.retry", locale)}</button>
            </form>
          </section>
"""
    else:
        body = render_blueprint_review(blueprint, content, locale)
    if blueprint.status != BlueprintStatus.FAILED:
        body = render_blueprint_sidebar(blueprint, locale) + body
    return _page(
        title=t("blueprint.review_title", locale),
        active="create",
        main=body,
        message=message,
        bottom=_render_start_pipeline("proposal", locale),
        locale=locale,
        eyebrow=status_label,
        content_class="content-grid blueprint-layout",
    )


def blueprint_status_label(status: BlueprintStatus | str, locale: str) -> str:
    value = status.value if isinstance(status, BlueprintStatus) else str(status)
    labels = {
        BlueprintStatus.PENDING.value: t("blueprint.pending", locale),
        BlueprintStatus.RUNNING.value: t("blueprint.running_short", locale),
        BlueprintStatus.SUCCEEDED.value: t("blueprint.succeeded", locale),
        BlueprintStatus.FAILED.value: t("blueprint.failed", locale),
    }
    return labels.get(value, value)


def render_book_workspace(
    book: Book,
    chapters: list[Chapter],
    canon: Canon | None,
    traces: list[RunTrace],
    volume_plans: list[VolumePlan] | None = None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    active_chapter = _next_chapter(chapters)
    all_first_ten_done = len(chapters) >= 10 and all(
        chapter.status == ChapterStatus.ACCEPTED for chapter in chapters[:10]
    )
    if all_first_ten_done:
        center = render_completed_progress(book, chapters, canon)
        aside = render_completed_aside(book, canon)
    else:
        center = f"""
      <section class="main-panel project-cockpit">
        <div class="panel-head">
          <div>
            <h1>{html.escape(book.title)}</h1>
            <p>{_book_status_label(book.status, locale)} · {html.escape(book.genre)} · {html.escape(book.audience)}</p>
          </div>
          <span class="status-pill trusted">{t("trusted_state.locked", locale)}</span>
        </div>
        <div class="metric-grid">
          <div><strong>{len([c for c in chapters if c.status == ChapterStatus.ACCEPTED])}</strong><span>{t("dashboard.accepted", locale)}</span></div>
          <div><strong>{len([c for c in chapters if c.status == ChapterStatus.AWAITING_REVIEW])}</strong><span>{t("dashboard.reviewing", locale)}</span></div>
          <div><strong>{len(chapters)}</strong><span>{t("dashboard.chapter_plan", locale)}</span></div>
        </div>
        <div class="actions state-link">
          <a class="button secondary" href="/book/{book.id}/state">{t("trusted_state.open", locale)}</a>
          <a class="button secondary" href="/book/{book.id}/quality">{t("quality.open", locale)}</a>
          <a class="button secondary" href="/book/{book.id}/export.md">{t("export.markdown", locale)}</a>
          <a class="button secondary" href="/book/{book.id}/export.json">{t("export.json", locale)}</a>
        </div>
        <h2>设定基础 <span class="muted">概览（来自可信设定）</span></h2>
        {_render_foundation_board(canon, locale)}
        {_render_volume_plan_board(volume_plans or [])}
        {_render_chapter_table(chapters, locale)}
      </section>
"""
        aside = f"""
      <aside class="right-panel cockpit-aside">
        <h2>{t("dashboard.next_action", locale)} <span class="status-pill trusted">2</span></h2>
        {_render_next_action(active_chapter, locale)}
        <h2>{t("batch.title", locale)}</h2>
        {_render_batch_action(book, active_chapter, locale)}
        <h2>目标字数</h2>
        {render_word_target_form(book)}
        <h2>{t("dashboard.recent_trace", locale)}</h2>
        {_render_trace_list(traces, locale)}
      </aside>
"""
    main = f"""
      {_render_book_sidebar(book, chapters, locale)}
      {center}
      {aside}
"""
    return _page(
        title=book.title,
        active="docs",
        main=main,
        message=message,
        bottom=_render_production_pipeline(None, locale),
        locale=locale,
        nav_book_id=book.id,
    )


def render_trusted_state_page(
    book: Book,
    canon: Canon | None,
    chapters: list[Chapter],
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
    proposal_revision: CanonProposalRevision | None = None,
) -> str:
    if isinstance(message, CanonProposalRevision) and proposal_revision is None:
        proposal_revision = message
        message = None
    locked = book.status in {BookStatus.CANON_LOCKED, BookStatus.PRODUCING, BookStatus.PAUSED}
    status_label = t("trusted_state.locked", locale) if locked else "可信设定提案 · 待确认"
    status_class = "trusted" if locked else "pending"
    page_title = t("trusted_state.title", locale) if locked else "开书定盘"
    main = f"""
      {_render_book_sidebar(book, chapters, locale)}
      <section class="main-panel canon-gate-main">
        <div class="panel-head">
          <div>
            <h1>{page_title}</h1>
            <p>{t("trusted_state.page_copy", locale)}</p>
          </div>
          <span class="status-pill {status_class}">{status_label}</span>
        </div>
        {render_canon_proposal_surface(book, canon, locked, proposal_revision)}
      </section>
      {render_canon_gate_aside(book, canon, chapters, locked, proposal_revision)}
"""
    return _page(
        title=t("trusted_state.title", locale),
        active="world",
        main=main,
        message=message,
        bottom=_render_start_pipeline("foundation", locale),
        locale=locale,
        eyebrow="开书定盘",
        content_class="content-grid canon-gate-layout",
        nav_book_id=book.id,
    )


def render_chapter_review(
    book: Book,
    chapters: list[Chapter],
    chapter: Chapter,
    canon: Canon | None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
    traces: list[RunTrace] | None = None,
) -> str:
    if chapter.status == ChapterStatus.RUNNING:
        main = f"""
      {_render_book_sidebar(book, chapters, locale)}
      {render_chapter_production_main(chapter)}
"""
        return _page(
            title=chapter.title,
            active="create",
            main=main,
            message=message,
            bottom=_render_production_pipeline(chapter.status, locale),
            locale=locale,
            eyebrow="章节生产",
            content_class="content-grid production-layout chapter-production-layout",
            nav_book_id=book.id,
        )

    main = f"""
      {_render_book_sidebar(book, chapters, locale)}
      <section class="reader-panel">
        <div class="chapter-toolbar">
          <div>
            <h1>{t("chapter.number", locale, number=chapter.number)} {html.escape(chapter.title)}</h1>
            <p>{_chapter_status_label(chapter.status, locale)} · {t("chapter.word_count", locale, count=chapter.word_count)}</p>
          </div>
          <a class="button secondary" href="/book/{book.id}">{t("action.back_to_project", locale)}</a>
        </div>
        {_render_chapter_body(chapter, locale)}
      </section>
      <aside class="right-panel review">
        {render_chapter_review_inspector(chapter, canon, locale, traces or [])}
      </aside>
"""
    return _page(
        title=chapter.title,
        active="docs",
        main=main,
        message=message,
        bottom=_render_production_pipeline(chapter.status, locale),
        locale=locale,
        content_class="content-grid human-review-layout",
        nav_book_id=book.id,
    )


def is_provider_config_complete(provider_config: ProviderConfig | None) -> bool:
    return bool(
        provider_config
        and provider_config.llm_base_url.strip()
        and provider_config.llm_model.strip()
        and provider_config.resolved_embedding_base_url().strip()
        and provider_config.embedding_model.strip()
    )


def _page(
    title: str,
    active: str,
    main: str,
    message: str | None,
    bottom: str,
    locale: str,
    db_path: Path | None = None,
    eyebrow: str | None = None,
    content_class: str = "content-grid",
    nav_book_id: int | None = None,
    status_strip: str | None = None,
) -> str:
    return render_app_page(
        title=title,
        active=active,
        main=main,
        bottom=bottom,
        message=message,
        locale=locale,
        db_path=db_path,
        eyebrow=eyebrow,
        content_class=content_class,
        nav_book_id=nav_book_id,
        status_strip=status_strip,
    )


def _render_book_sidebar(book: Book, chapters: list[Chapter], locale: str) -> str:
    return render_project_sidebar(book, chapters, locale=locale)


def _render_foundation_board(canon: Canon | None, locale: str) -> str:
    if canon is None:
        return f"<p>{t('trusted_state.missing', locale)}</p>"
    content = canon.content
    cards = [
        (t("trusted_state.world_rules", locale), content.get("world_rules", [])),
        (t("trusted_state.characters", locale), content.get("characters", [])),
        (t("trusted_state.foreshadowing", locale), content.get("foreshadowing", [])),
        (t("trusted_state.chapter_summaries", locale), content.get("chapter_summaries", [])),
    ]
    return (
        "<div class='card-grid'>"
        + "".join(
            f"<section class='data-card'><h3>{label}</h3>{_render_value(value)}</section>"
            for label, value in cards
        )
        + "</div>"
    )


def _render_volume_plan_board(volume_plans: list[VolumePlan]) -> str:
    if not volume_plans:
        return ""
    plan = volume_plans[0]
    rows = [
        ("卷级目标", _render_nested(plan.core_conflict)),
        ("节奏曲线", "；".join(_render_nested(item) for item in plan.pacing_curve[:4])),
        ("爽点兑现", "；".join(_render_nested(item) for item in plan.payoff_distribution[:4])),
        ("关键转折", "；".join(_render_nested(item) for item in plan.key_turns[:4])),
        ("阶段承诺", "；".join(_render_nested(item) for item in plan.commitments[:4])),
    ]
    content = "".join(
        f"<p><strong>{html.escape(label)}</strong> {value}</p>" for label, value in rows if value
    )
    return f"<section class='data-card'><h3>{html.escape(plan.title)}</h3>{content}</section>"


def _render_chapter_table(chapters: list[Chapter], locale: str) -> str:
    rows = "".join(
        f"<tr><td>{chapter.number:02d}</td><td><a href='/chapter/{chapter.id}'>{html.escape(chapter.title)}</a></td>"
        f"<td>{_chapter_status_label(chapter.status, locale)}</td><td>{html.escape(chapter.summary)}</td></tr>"
        for chapter in chapters
    )
    return f"<section class='table-card'><h2>{t('dashboard.chapter_plan', locale)}</h2><table><tbody>{rows}</tbody></table></section>"


def _render_next_action(chapter: Chapter | None, locale: str) -> str:
    if chapter is None:
        return f"<p>{t('dashboard.all_done', locale)}</p>"
    if chapter.status == ChapterStatus.AWAITING_REVIEW:
        return f"<a class='button' href='/chapter/{chapter.id}'>{t('action.review_chapter', locale)}</a>"
    if chapter.status == ChapterStatus.ACCEPTED:
        return f"<p>{t('dashboard.all_done', locale)}</p>"
    return f"""
      <p>{t("dashboard.next_chapter", locale, number=chapter.number, title=html.escape(chapter.title))}</p>
      <form method="post" action="/run-chapter">
        <input type="hidden" name="chapter_id" value="{chapter.id}">
        <button type="submit">{t("action.run_chapter", locale)}</button>
      </form>
"""


def _render_batch_action(book: Book, chapter: Chapter | None, locale: str) -> str:
    if book.status == BookStatus.PAUSED:
        return f"<p>{t('batch.paused', locale)}</p>"
    if chapter is None or book.id is None:
        return f"<p>{t('dashboard.all_done', locale)}</p>"
    return f"""
      <form method="post" action="/run-chapter-batch" class="compact-form">
        <input type="hidden" name="book_id" value="{book.id}">
        <label>{t("batch.limit", locale)}<input name="limit" type="number" min="1" max="10" value="2"></label>
        <button type="submit">{t("batch.run", locale)}</button>
      </form>
"""


def _render_trace_list(traces: list[RunTrace], locale: str) -> str:
    if not traces:
        return f"<p>{t('dashboard.no_trace', locale)}</p>"
    return (
        "<div class='stack-list'>"
        + "".join(
            f"<p>{t('dashboard.trace_item', locale, stage=_trace_stage(trace.stage), time=trace.created_at.strftime('%H:%M'))}</p>"
            for trace in traces[-4:]
        )
        + "</div>"
    )


def _render_chapter_body(chapter: Chapter, locale: str) -> str:
    if chapter.status == ChapterStatus.PLANNED:
        return f"""
          <div class="empty-box">
            <p>{t("chapter.not_started", locale)}</p>
            <form method="post" action="/run-chapter">
              <input type="hidden" name="chapter_id" value="{chapter.id}">
              <button type="submit">{t("action.run_chapter", locale)}</button>
            </form>
          </div>
"""
    if chapter.status == ChapterStatus.ACCEPTED:
        text = chapter.final_text or chapter.revised_text or chapter.draft_text
    else:
        text = chapter.revised_text or chapter.draft_text or chapter.final_text
    return f"""
      <article class="chapter-text">{html.escape(text).replace(chr(10), "<br>")}</article>
"""


def _render_start_pipeline(active: str | None, locale: str) -> str:
    steps = [
        ("open_book", t("pipeline.open_book", locale)),
        ("proposal", t("blueprint.review_title", locale)),
        ("foundation", t("pipeline.foundation", locale)),
        ("generate", t("pipeline.generate", locale)),
        ("review", t("pipeline.review", locale)),
        ("accept", t("pipeline.accept", locale)),
    ]
    return _pipeline(steps, active)


def _render_first_launch_pipeline(locale: str) -> str:
    steps = [
        PipelineStep("open_book", t("pipeline.open_book", locale), "locked", "设定方向与边界", "▣"),
        PipelineStep(
            "foundation", t("pipeline.foundation", locale), "locked", "确认世界与可信设定", "▤"
        ),
        PipelineStep("generate", t("pipeline.generate", locale), "locked", "AI 生成故事内容", "✦"),
        PipelineStep("review", t("pipeline.review", locale), "locked", "人工审核与修正", "✓"),
        PipelineStep("accept", t("pipeline.accept", locale), "locked", "可信设定成为事实源", "◇"),
    ]
    return render_pipeline(steps, title="生产流水线", element_id="launch-pipeline")


def _render_production_pipeline(active: ChapterStatus | None, locale: str) -> str:
    status_map = {
        ChapterStatus.RUNNING: "draft",
        ChapterStatus.AWAITING_REVIEW: "review",
        ChapterStatus.ACCEPTED: "accept",
    }
    steps = [
        ("plan", t("pipeline.plan", locale)),
        ("context", t("pipeline.context", locale)),
        ("draft", t("pipeline.draft_cn", locale)),
        ("extract", t("pipeline.extract", locale)),
        ("audit", t("pipeline.audit", locale)),
        ("revise", t("pipeline.revise", locale)),
        ("review", t("pipeline.review", locale)),
        ("accept", t("pipeline.accept", locale)),
    ]
    active_step = status_map.get(active) if active is not None else None
    return _pipeline(steps, active_step)


def _pipeline(steps: list[tuple[str, str]], active: str | None) -> str:
    active_index = next((index for index, (key, _) in enumerate(steps) if key == active), None)
    pipeline_steps = []
    for index, (key, label) in enumerate(steps):
        if active_index is None:
            state = "pending"
            note = "待开始"
        elif index < active_index:
            state = "done"
            note = "已完成"
        elif index == active_index:
            state = "current"
            note = "当前阶段"
        else:
            state = "pending"
            note = "待开始"
        icon = "✓" if state == "done" else str(index + 1)
        pipeline_steps.append(PipelineStep(key=key, label=label, state=state, note=note, icon=icon))
    return render_pipeline(pipeline_steps)


def _input(
    name: str,
    label: str,
    placeholder: str = "",
    value: str = "",
    required: bool = False,
    input_type: str = "text",
) -> str:
    return (
        f'<label>{label}<input name="{name}" type="{input_type}" value="{value}" '
        f'placeholder="{html.escape(placeholder, quote=True)}"{" required" if required else ""}></label>'
    )


def _select(name: str, label: str, empty_label: str, options: tuple[str, ...]) -> str:
    option_html = [f'<option value="">{html.escape(empty_label)}</option>']
    option_html.extend(
        f'<option value="{html.escape(option, quote=True)}">{html.escape(option)}</option>'
        for option in options
    )
    return f'<label>{label}<select name="{name}">{"".join(option_html)}</select></label>'


def _textarea(name: str, label: str, placeholder: str = "") -> str:
    return (
        f'<label>{label}<textarea name="{name}" '
        f'placeholder="{html.escape(placeholder, quote=True)}"></textarea></label>'
    )


def _render_value(value: Any) -> str:
    if isinstance(value, list):
        visible_items = [item for item in value if not _is_low_information_state_item(item)]
        if not visible_items:
            return "<p>—</p>"
        return (
            "<ul>"
            + "".join(f"<li>{_render_nested(item)}</li>" for item in visible_items[:6])
            + "</ul>"
        )
    if isinstance(value, dict):
        return (
            "<dl>"
            + "".join(
                f"<dt>{_label_key(key)}</dt><dd>{_render_nested(item)}</dd>"
                for key, item in value.items()
            )
            + "</dl>"
        )
    if value in (None, ""):
        return "<p>—</p>"
    return f"<p>{html.escape(str(value))}</p>"


def _render_nested(value: Any) -> str:
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
            f"{_label_key(k)}：{_render_nested(v)}"
            for k, v in value.items()
            if not _is_internal_state_key(k)
        )
    if isinstance(value, list):
        return "、".join(_render_nested(item) for item in value)
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
    head = f"{actors}：{relation}" if actors and relation else actors or relation
    return f"{head}。{detail}" if detail and head else head


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


def _section_label(value: Any) -> str:
    return {
        "world_rules": "世界规则",
        "characters": "人物",
        "factions": "势力",
        "locations": "地点",
        "relationships": "关系",
        "foreshadowing": "伏笔账本",
        "chapter_summaries": "章节摘要",
        "state_history": "变化历史",
    }.get(str(value or ""), "")


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


def _is_internal_state_key(key: object) -> bool:
    return str(key) in {"chapter_title", "updated_at", "accepted_at"}


def _unknown_target_detail(value: dict) -> str:
    if str(value.get("name") or value.get("target") or "").strip() != "待确认":
        return ""
    return str(value.get("detail") or value.get("change") or "").strip()


def _is_low_information_state_item(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if str(value.get("name") or value.get("target") or "").strip() != "待确认":
        return False
    detail = str(value.get("detail") or value.get("change") or "").strip()
    low_information_values = {
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
    return detail in low_information_values


def _label_key(key: object) -> str:
    labels = {
        "chapter": "章节",
        "background": "背景",
        "changes": "变化",
        "content": "摘要",
        "description": "说明",
        "direction": "方向",
        "from": "起点",
        "title": "标题",
        "goal": "目标",
        "name": "名称",
        "hook": "钩子",
        "identity": "身份",
        "impact": "影响",
        "mechanism": "机制",
        "motivation": "动机",
        "personality": "性格",
        "premise": "前提",
        "role": "定位",
        "rules": "规则",
        "setting": "背景",
        "detail": "内容",
        "trait": "特质",
        "audience": "目标读者",
        "genre": "题材",
        "summary": "摘要",
        "target": "对象",
        "to": "终点",
        "trigger": "触发",
        "type": "类型",
        "word_count": "字数",
    }
    return html.escape(labels.get(str(key), str(key)))


def _next_chapter(chapters: list[Chapter]) -> Chapter | None:
    for chapter in chapters:
        if chapter.status != ChapterStatus.ACCEPTED:
            return chapter
    return None


def _book_status_label(status: BookStatus | str, locale: str) -> str:
    value = status.value if isinstance(status, BookStatus) else str(status)
    return {
        BookStatus.DRAFT.value: t("book.status_draft", locale),
        BookStatus.CANON_LOCKED.value: t("book.status_locked", locale),
        BookStatus.PRODUCING.value: t("book.status_producing", locale),
        BookStatus.PAUSED.value: t("book.status_paused", locale),
    }.get(value, value)


def _chapter_status_label(status: ChapterStatus | str, locale: str) -> str:
    value = status.value if isinstance(status, ChapterStatus) else str(status)
    return {
        ChapterStatus.PLANNED.value: t("chapter.status_planned", locale),
        ChapterStatus.RUNNING.value: t("chapter.status_running", locale),
        ChapterStatus.AWAITING_REVIEW.value: t("chapter.status_review", locale),
        ChapterStatus.NEEDS_REVISION.value: t("chapter.status_revision", locale),
        ChapterStatus.ACCEPTED.value: t("chapter.status_accepted", locale),
    }.get(value, value)


def _trace_stage(stage: str) -> str:
    return {"chapter_pipeline": "章节生产", "accept_chapter": "人工批准"}.get(stage, stage)
