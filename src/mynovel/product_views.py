from __future__ import annotations

import html
from pathlib import Path
from typing import Any

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
)
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.workflows.open_book import title_options_from_blueprint


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
        main = _render_project_home(books, blueprints, configured, locale)
    else:
        main = _render_empty_home(provider_config, configured, locale)
    return _page(
        title=t("app.title", locale),
        active="workspace",
        main=main,
        message=message,
        bottom=_render_start_pipeline(None, locale),
        locale=locale,
        db_path=db_path,
    )


def render_new_book_page(
    provider_config: ProviderConfig | None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    disabled = "" if is_provider_config_complete(provider_config) else " disabled"
    main = f"""
      <aside class="side-panel">
        <h2>{t("new_book.title", locale)}</h2>
        <p>{t("new_book.subtitle", locale)}</p>
        <ol class="step-list">
          <li class="active">{t("new_book.step_settings", locale)}</li>
          <li>{t("new_book.step_proposal", locale)}</li>
          <li>{t("new_book.step_foundation", locale)}</li>
        </ol>
      </aside>
      <section class="main-panel">
        <div class="panel-head">
          <div>
            <h1>{t("new_book.settings_title", locale)}</h1>
            <p>{t("new_book.settings_intro", locale)}</p>
          </div>
          <span class="status-pill pending">{t("status.pending", locale)}</span>
        </div>
        <form method="post" action="/open-book" class="form-grid">
          {_input("idea", t("book.idea", locale), t("book.idea_placeholder", locale), required=True)}
          {_input("genre", t("book.genre", locale), "奇幻成长")}
          {_input("audience", t("book.audience", locale), "喜欢连载爽点和悬念的读者")}
          {_input("selling_points", t("book.selling_points", locale), "持续揭秘、角色成长、章节钩子")}
          {_textarea("constraints", t("book.constraints", locale), "不写崩坏人设，不让关键设定前后矛盾")}
          {_input("style_reference", t("book.style_reference", locale), "清爽、克制、节奏明确")}
          <div class="split">
            {_input("length_goal", t("book.length_goal", locale), "120000 字")}
            {_input("serial_rhythm", t("book.serial_rhythm", locale), "每天 1 章")}
          </div>
          <div class="actions">
            <a class="button secondary" href="/">{t("action.back", locale)}</a>
            <button type="submit"{disabled}>{t("book.create", locale)}</button>
          </div>
        </form>
      </section>
      <aside class="right-panel">
        <h2>{t("new_book.preview_title", locale)}</h2>
        <div class="stack-list">
          <p>{t("blueprint.title_options", locale)}</p>
          <p>{t("blueprint.selling_points", locale)}</p>
          <p>{t("blueprint.protagonist", locale)}</p>
          <p>{t("blueprint.world", locale)}</p>
          <p>{t("blueprint.reader_promises", locale)}</p>
        </div>
      </aside>
"""
    return _page(
        title=t("new_book.title", locale),
        active="create",
        main=main,
        message=message,
        bottom=_render_start_pipeline("open_book", locale),
        locale=locale,
    )


def render_blueprint_page(
    db_path: Path,
    provider_config: ProviderConfig | None,
    blueprint: OpenBookBlueprint,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    _ = db_path, provider_config
    content = blueprint.content or {}
    status_label = blueprint_status_label(blueprint.status, locale)
    if blueprint.status in {BlueprintStatus.PENDING, BlueprintStatus.RUNNING}:
        body = f"""
          <section class="main-panel single">
            <h1>{t("blueprint.generating_title", locale)}</h1>
            <p>{t("blueprint.running", locale)}</p>
            <div class="actions">
              <a class="button" href="/blueprint/{blueprint.id}">{t("blueprint.refresh", locale)}</a>
            </div>
          </section>
"""
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
        body = _render_blueprint_review(blueprint, content, locale)
    return _page(
        title=t("blueprint.review_title", locale),
        active="create",
        main=body,
        message=message,
        bottom=_render_start_pipeline("proposal", locale),
        locale=locale,
        eyebrow=status_label,
    )


def render_structured_blueprint(
    content: dict[str, Any],
    locale: str,
    include_title_options: bool = True,
) -> str:
    if not content:
        return ""
    sections = [
        ("blueprint.title_options", content.get("title_options")),
        ("blueprint.genre", content.get("genre")),
        ("blueprint.audience", content.get("audience")),
        ("blueprint.selling_points", content.get("selling_points")),
        ("blueprint.protagonist", content.get("protagonist")),
        ("blueprint.world", content.get("world")),
        ("blueprint.central_conflict", content.get("central_conflict")),
        ("blueprint.reader_promises", content.get("reader_promises")),
        ("blueprint.chapter_directions", content.get("chapter_directions")),
    ]
    blocks = []
    for key, value in sections:
        if key == "blueprint.title_options" and not include_title_options:
            continue
        if value in (None, "", [], {}):
            continue
        blocks.append(
            f"<section class='data-card'><h3>{t(key, locale)}</h3>{_render_value(value)}</section>"
        )
    return "".join(blocks)


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
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    active_chapter = _next_chapter(chapters)
    main = f"""
      {_render_book_sidebar(book, chapters, locale)}
      <section class="main-panel">
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
        {_render_foundation_board(canon, locale)}
        {_render_chapter_table(chapters, locale)}
      </section>
      <aside class="right-panel">
        <h2>{t("dashboard.next_action", locale)}</h2>
        {_render_next_action(active_chapter, locale)}
        <h2>{t("dashboard.recent_trace", locale)}</h2>
        {_render_trace_list(traces, locale)}
      </aside>
"""
    return _page(
        title=book.title,
        active="create",
        main=main,
        message=message,
        bottom=_render_production_pipeline(None, locale),
        locale=locale,
    )


def render_chapter_review(
    book: Book,
    chapters: list[Chapter],
    chapter: Chapter,
    canon: Canon | None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
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
        {_render_review_inspector(chapter, canon, locale)}
      </aside>
"""
    return _page(
        title=chapter.title,
        active="review",
        main=main,
        message=message,
        bottom=_render_production_pipeline(chapter.status, locale),
        locale=locale,
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
) -> str:
    db_hint = (
        f"<span>{t('app.local_database', locale)}：{html.escape(str(db_path))}</span>"
        if db_path
        else ""
    )
    return f"""<!doctype html>
<html lang="{locale}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{_css()}</style>
</head>
<body>
  <div class="app-shell">
    <nav class="rail">
      <strong>MyNovel</strong>
      {_nav_item("/", t("nav.workspace", locale), active == "workspace")}
      {_nav_item("/books/new", t("nav.create", locale), active == "create")}
      {_nav_item("/", t("nav.docs", locale), False)}
      {_nav_item("/", t("nav.review", locale), active == "review")}
      {_nav_item("/", t("nav.settings", locale), False)}
    </nav>
    <main class="workspace">
      <header class="topbar">
        <div><span class="eyebrow">{html.escape(eyebrow or t("app.product_mode", locale))}</span></div>
        <div class="top-actions">{db_hint}<span>{t("app.local_first", locale)}</span></div>
      </header>
      {f"<p class='notice'>{html.escape(message)}</p>" if message else ""}
      <div class="content-grid">{main}</div>
      {bottom}
    </main>
  </div>
</body>
</html>
"""


def _render_empty_home(
    provider_config: ProviderConfig | None,
    configured: bool,
    locale: str,
) -> str:
    status = t("model.ready", locale) if configured else t("model.not_ready", locale)
    return f"""
      <section class="empty-hero">
        <div class="book-mark">◇</div>
        <h1>{t("home.empty_title", locale)}</h1>
        <p>{t("home.empty_copy", locale)}</p>
        <div class="actions center">
          <a class="button" href="/books/new">{t("home.create_first", locale)}</a>
          <a class="button secondary" href="/">{t("home.import_project", locale)}</a>
        </div>
        <div class="local-note"><strong>{t("home.local_first", locale)}</strong><span>{t("home.local_copy", locale)}</span></div>
      </section>
      <aside class="right-panel">
        <h2>{t("home.recent_projects", locale)}</h2>
        <div class="empty-box">{t("home.empty_recent", locale)}</div>
        <h2>{t("model.status", locale)}</h2>
        <div class="setup-card">
          <strong>{status}</strong>
          <a class="button secondary" href="#model-form">{t("model.configure", locale)}</a>
        </div>
        <h2>{t("trusted_state.title", locale)}</h2>
        <p>{t("trusted_state.empty_hint", locale)}</p>
      </aside>
      <aside class="right-panel model-form" id="model-form">
        <h2>{t("model.title", locale)}</h2>
        {_render_provider_form(provider_config, locale)}
      </aside>
"""


def _render_project_home(
    books: list[Book],
    blueprints: list[OpenBookBlueprint],
    configured: bool,
    locale: str,
) -> str:
    rows = "".join(
        f"<a class='project-row' href='/book/{book.id}'><strong>{html.escape(book.title)}</strong>"
        f"<span>{_book_status_label(book.status, locale)}</span></a>"
        for book in books
    )
    blueprint_note = ""
    if blueprints:
        latest = blueprints[0]
        blueprint_note = (
            f"<a class='project-row' href='/blueprint/{latest.id}'><strong>{t('blueprint.review_title', locale)}</strong>"
            f"<span>{blueprint_status_label(latest.status, locale)}</span></a>"
        )
    model_status = t("model.ready", locale) if configured else t("model.not_ready", locale)
    return f"""
      <section class="main-panel single">
        <div class="panel-head">
          <div>
            <h1>{t("home.workspace_title", locale)}</h1>
            <p>{t("home.workspace_copy", locale)}</p>
          </div>
          <a class="button" href="/books/new">{t("home.create_first", locale)}</a>
        </div>
        <div class="project-list">{rows}{blueprint_note}</div>
        <div class="setup-card"><strong>{model_status}</strong><span>{t("app.local_first", locale)}</span></div>
      </section>
"""


def _render_provider_form(config: ProviderConfig | None, locale: str) -> str:
    config = config or ProviderConfig(
        llm_base_url="",
        llm_model="",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="",
        rerank_use_llm_credentials=True,
    )
    embedding_checked = " checked" if config.embedding_use_llm_credentials else ""
    rerank_checked = " checked" if config.rerank_use_llm_credentials else ""
    return f"""
      <form method="post" action="/provider-config" class="compact-form">
        {_input("llm_base_url", t("provider.llm_base_url", locale), "填写服务接口地址", _field(config.llm_base_url), True)}
        {_input("llm_api_key", t("provider.llm_api_key", locale), "", _field(config.llm_api_key), False, "password")}
        {_input("llm_model", t("provider.llm_model", locale), "填写对话模型名称", _field(config.llm_model), True)}
        {_input("embedding_model", t("provider.embedding_model", locale), "填写检索模型名称", _field(config.embedding_model), True)}
        <label class="inline-check"><input name="embedding_use_llm_credentials" type="checkbox" value="1"{embedding_checked}>{t("provider.embedding_use_llm", locale)}</label>
        {_input("embedding_base_url", t("provider.embedding_base_url", locale), "可留空复用上方接口", _field(config.embedding_base_url))}
        {_input("embedding_api_key", t("provider.embedding_api_key", locale), "", _field(config.embedding_api_key), False, "password")}
        {_input("rerank_model", t("provider.rerank_model", locale), "可选", _field(config.rerank_model))}
        <label class="inline-check"><input name="rerank_use_llm_credentials" type="checkbox" value="1"{rerank_checked}>{t("provider.rerank_use_llm", locale)}</label>
        {_input("rerank_base_url", t("provider.rerank_base_url", locale), "可选", _field(config.rerank_base_url))}
        {_input("rerank_api_key", t("provider.rerank_api_key", locale), "", _field(config.rerank_api_key), False, "password")}
        <button type="submit">{t("provider.save", locale)}</button>
      </form>
"""


def _render_blueprint_review(
    blueprint: OpenBookBlueprint, content: dict[str, Any], locale: str
) -> str:
    title_options = title_options_from_blueprint(content)
    options = "".join(
        f'<label class="choice"><input type="radio" name="selected_title" '
        f'value="{html.escape(title, quote=True)}" required><span>{html.escape(title)}</span></label>'
        for title in title_options
    )
    proposal = render_structured_blueprint(content, locale, include_title_options=False)
    return f"""
      <section class="main-panel">
        <div class="panel-head">
          <div>
            <h1>{t("blueprint.review_title", locale)}</h1>
            <p>{t("blueprint.review_copy", locale)}</p>
          </div>
          <span class="status-pill pending">{t("trusted_state.not_written", locale)}</span>
        </div>
        <div class="card-grid">{proposal}</div>
      </section>
      <aside class="right-panel">
        <h2>{t("blueprint.choose_direction", locale)}</h2>
        <form method="post" action="/accept-blueprint" class="compact-form">
          <input type="hidden" name="blueprint_id" value="{blueprint.id}">
          <h3>{t("blueprint.title_options", locale)}</h3>
          <div class="choice-list">{options}</div>
          {_textarea("revision_notes", t("blueprint.revision_notes", locale), "也可以先写修改意见，再让系统重做")}
          <button type="submit">{t("blueprint.continue", locale)}</button>
        </form>
        <form method="post" action="/revise-blueprint" class="actions">
          <input type="hidden" name="blueprint_id" value="{blueprint.id}">
          <input type="hidden" name="revision_notes" value="请重新生成一组方向，保持题材但扩大差异。">
          <button class="secondary" type="submit">{t("blueprint.regenerate", locale)}</button>
        </form>
      </aside>
"""


def _render_book_sidebar(book: Book, chapters: list[Chapter], locale: str) -> str:
    rows = "".join(
        f"<a class='chapter-row {chapter.status.value}' href='/chapter/{chapter.id}'>"
        f"<span>{chapter.number:02d}</span><strong>{html.escape(chapter.title)}</strong>"
        f"<em>{_chapter_status_label(chapter.status, locale)}</em></a>"
        for chapter in chapters
    )
    return f"""
      <aside class="side-panel book-side">
        <h2>{html.escape(book.title)}</h2>
        <p>{html.escape(book.genre)} · {html.escape(book.audience)}</p>
        <span class="status-pill trusted">{_book_status_label(book.status, locale)}</span>
        <h3>{t("dashboard.chapter_queue", locale)}</h3>
        <div class="chapter-list">{rows}</div>
      </aside>
"""


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
    text = chapter.final_text or chapter.revised_text or chapter.draft_text
    return f"""
      <article class="chapter-text">{html.escape(text).replace(chr(10), "<br>")}</article>
"""


def _render_review_inspector(chapter: Chapter, canon: Canon | None, locale: str) -> str:
    if chapter.status == ChapterStatus.PLANNED:
        return f"<h2>{t('review.waiting', locale)}</h2><p>{t('chapter.not_started', locale)}</p>"
    issue_rows = "".join(
        f"<li><span>{html.escape(str(issue.get('title', '')))}</span><em>{t('review.fixed', locale) if issue.get('resolved') else t('review.needs_confirm', locale)}</em></li>"
        for issue in chapter.audit_report.get("issues", [])
        if isinstance(issue, dict)
    )
    delta_rows = "".join(
        f"<li><span>{html.escape(str(change.get('type', '')))}：{html.escape(str(change.get('target', '')))}</span><em>{html.escape(str(change.get('change', '')))}</em></li>"
        for change in chapter.state_delta.get("changes", [])
        if isinstance(change, dict)
    )
    canon_version = canon.version if canon else 0
    action = ""
    if chapter.status == ChapterStatus.AWAITING_REVIEW:
        action = f"""
          <form method="post" action="/repair-chapter" class="compact-form action-form">
            <input type="hidden" name="chapter_id" value="{chapter.id}">
            <label>{t("chapter.repair_note", locale)}<textarea name="reviewer_note" placeholder="{t("chapter.repair_placeholder", locale)}"></textarea></label>
            <button class="secondary" type="submit">{t("action.repair_with_ai", locale)}</button>
          </form>
          <form method="post" action="/request-revision" class="compact-form action-form">
            <input type="hidden" name="chapter_id" value="{chapter.id}">
            <label>{t("chapter.reviewer_note", locale)}<textarea name="reviewer_note" placeholder="{t("chapter.note_placeholder", locale)}"></textarea></label>
            <button class="secondary" type="submit">{t("action.return_for_revision", locale)}</button>
          </form>
          <form id="approve-form" method="post" action="/approve-chapter" class="compact-form action-form">
            <input type="hidden" name="chapter_id" value="{chapter.id}">
            <label>{t("chapter.accept_note", locale)}<textarea name="reviewer_note" placeholder="{t("chapter.accept_placeholder", locale)}"></textarea></label>
            <button type="submit">{t("action.accept_to_trusted_state", locale)}</button>
          </form>
"""
    elif chapter.status == ChapterStatus.ACCEPTED:
        action = f"""
          <div class="actions">
            <a class="button" href="/chapter/{chapter.id}/export">{t("action.export_chapter", locale)}</a>
          </div>
"""
    return f"""
      <h2>{t("review.audit_issues", locale)}</h2>
      <ul class="review-list">{issue_rows}</ul>
      <h2>{t("review.state_delta", locale)}</h2>
      <p>{t("trusted_state.current_version", locale, version=canon_version)}</p>
      <ul class="review-list">{delta_rows}</ul>
      {action}
"""


def _render_start_pipeline(active: str | None, locale: str) -> str:
    steps = [
        ("open_book", t("pipeline.open_book", locale)),
        ("foundation", t("pipeline.foundation", locale)),
        ("generate", t("pipeline.generate", locale)),
        ("review", t("pipeline.review", locale)),
        ("accept", t("pipeline.accept", locale)),
    ]
    return _pipeline(steps, active)


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
    return _pipeline(steps, status_map.get(active))


def _pipeline(steps: list[tuple[str, str]], active: str | None) -> str:
    items = "".join(
        f"<span class='pipe-step {'active' if key == active else ''}'>{label}</span>"
        for key, label in steps
    )
    return f"<footer class='pipeline'>{items}</footer>"


def _nav_item(href: str, label: str, active: bool) -> str:
    return f"<a class='{'active' if active else ''}' href='{href}'>{label}</a>"


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


def _textarea(name: str, label: str, placeholder: str = "") -> str:
    return (
        f'<label>{label}<textarea name="{name}" '
        f'placeholder="{html.escape(placeholder, quote=True)}"></textarea></label>'
    )


def _field(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def _render_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "<p>—</p>"
        return "<ul>" + "".join(f"<li>{_render_nested(item)}</li>" for item in value[:6]) + "</ul>"
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
        return "；".join(f"{_label_key(k)}：{html.escape(str(v))}" for k, v in value.items())
    if isinstance(value, list):
        return "、".join(html.escape(str(item)) for item in value)
    return html.escape(str(value))


def _label_key(key: object) -> str:
    labels = {
        "chapter": "章节",
        "direction": "方向",
        "title": "标题",
        "goal": "目标",
        "name": "名称",
        "hook": "钩子",
        "premise": "前提",
        "detail": "内容",
        "audience": "目标读者",
        "genre": "题材",
        "summary": "摘要",
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


def _css() -> str:
    return """
    :root{color-scheme:light;--bg:#f7f8f4;--panel:#fffefa;--ink:#1d2822;--muted:#68756d;--line:#dbe2d8;--accent:#426f4e;--accent-2:#edf4ea;--warn:#c47a16;--danger:#b94435}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}
    a{color:inherit;text-decoration:none}.app-shell{display:grid;grid-template-columns:136px 1fr;min-height:100vh}.rail{border-right:1px solid var(--line);background:#fbfcf8;padding:22px 16px;display:flex;flex-direction:column;gap:12px}.rail strong{font-size:22px;margin-bottom:18px}.rail a{border-radius:8px;padding:12px 10px;color:var(--muted)}.rail a.active,.rail a:hover{background:var(--accent-2);color:var(--accent)}
    .workspace{display:flex;flex-direction:column;min-width:0}.topbar{height:58px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 24px;background:#fffefa}.top-actions{display:flex;gap:18px;color:var(--muted);font-size:13px}.eyebrow{color:var(--muted);font-size:13px}.notice{margin:16px 24px 0;color:var(--warn)}
    .content-grid{display:grid;grid-template-columns:280px minmax(0,1fr) 360px;gap:12px;padding:12px;flex:1;min-height:0}.main-panel,.right-panel,.side-panel,.reader-panel,.empty-hero{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:18px}.main-panel.single{grid-column:1 / -1}.empty-hero{grid-column:1 / 3;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;min-height:560px}.book-mark{font-size:42px;color:var(--accent);margin-bottom:20px}
    h1{margin:0 0 8px;font-size:26px;line-height:1.2}h2{margin:0 0 12px;font-size:17px}h3{margin:18px 0 10px;font-size:14px;color:var(--muted)}p{margin:0 0 12px;color:var(--muted);line-height:1.6}.panel-head,.chapter-toolbar{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:16px}
    .button,button{display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:0;border-radius:7px;background:var(--accent);color:#fff;cursor:pointer;font:inherit;font-weight:650;padding:9px 14px}.button.secondary,button.secondary{background:#fff;color:var(--ink);border:1px solid var(--line)}button:disabled,input:disabled{opacity:.55;cursor:not-allowed}.actions{display:flex;gap:10px;flex-wrap:wrap}.actions.center{justify-content:center}.compact-form,.form-grid{display:grid;gap:12px}.form-grid{grid-template-columns:1fr 1fr}.form-grid label:first-child,.form-grid label:nth-child(5),.form-grid .actions{grid-column:1 / -1}.split{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    label{display:grid;gap:6px;color:var(--muted);font-size:13px}input,textarea{width:100%;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);font:inherit;min-height:42px;padding:9px 11px}textarea{min-height:90px;resize:vertical}.inline-check{display:flex;align-items:center;gap:8px;color:var(--ink)}.inline-check input{width:auto;min-height:auto}
    .status-pill{display:inline-flex;align-items:center;border-radius:999px;padding:5px 10px;font-size:13px;background:#f4efe4;color:var(--warn)}.status-pill.trusted{background:var(--accent-2);color:var(--accent)}.pending{color:var(--warn)}.danger{color:var(--danger)}.local-note,.setup-card,.empty-box{border:1px solid var(--line);border-radius:8px;padding:14px;background:#fbfcf8}.local-note{display:grid;gap:4px;margin-top:24px;max-width:360px}.setup-card{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}
    .step-list{margin:24px 0;padding-left:20px;color:var(--muted)}.step-list li{margin:14px 0}.step-list .active{color:var(--accent);font-weight:700}.stack-list{display:grid;gap:8px}.stack-list p,.project-row{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.project-list{display:grid;gap:10px}.project-row{display:flex;justify-content:space-between;align-items:center}
    .card-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.data-card,.table-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:14px}.data-card h3{margin-top:0;color:var(--ink);font-size:15px}ul{margin:0;padding-left:20px}li{margin:5px 0;line-height:1.5}dl{display:grid;grid-template-columns:96px 1fr;gap:8px 12px}dt{color:var(--muted)}dd{margin:0}
    .metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}.metric-grid div{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.metric-grid strong{font-size:26px;display:block}.metric-grid span{color:var(--muted);font-size:13px}.chapter-list{display:grid;gap:6px}.chapter-row{display:grid;grid-template-columns:36px 1fr auto;gap:8px;align-items:center;border-radius:8px;padding:10px;color:var(--muted)}.chapter-row:hover,.chapter-row.awaiting_review,.chapter-row.accepted{background:var(--accent-2);color:var(--accent)}.chapter-row em{font-style:normal;font-size:12px}
    table{width:100%;border-collapse:collapse;font-size:14px}td{border-bottom:1px solid var(--line);padding:10px 8px;vertical-align:top}.reader-panel{grid-column:2 / 3}.chapter-text{min-height:560px;border-top:1px solid var(--line);padding:28px 64px;font-size:19px;line-height:2;color:#222;white-space:normal}.note-box{border-top:1px solid var(--line);padding-top:14px}.review-list{display:grid;gap:8px;padding:0;list-style:none}.review-list li{border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px;display:grid;gap:4px}.review-list em{font-style:normal;color:var(--muted);font-size:12px}
    .choice-list{display:grid;gap:8px}.choice{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:11px;color:var(--ink)}.choice input{width:auto;min-height:auto}.action-form{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}.pipeline{height:92px;border-top:1px solid var(--line);background:#fffefa;display:flex;align-items:center;gap:16px;padding:0 24px;overflow:auto}.pipe-step{white-space:nowrap;border:1px solid var(--line);border-radius:999px;padding:8px 14px;color:var(--muted)}.pipe-step.active{border-color:var(--warn);color:var(--warn);background:#fff7ea}
    @media(max-width:1100px){.app-shell{grid-template-columns:82px 1fr}.rail strong{font-size:14px}.content-grid{grid-template-columns:1fr}.empty-hero,.reader-panel{grid-column:auto}.form-grid,.card-grid,.split{grid-template-columns:1fr}}
    """
