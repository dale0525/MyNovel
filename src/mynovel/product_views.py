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
    VolumePlan,
)
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.product_components import (
    render_accepted_result,
    render_canon_gate_aside,
    render_canon_gate_main,
    render_chapter_production_aside,
    render_chapter_production_main,
    render_impact_scope,
    render_model_setup_content,
    render_review_tabs,
)
from mynovel.ui_shell import PipelineStep, render_app_page, render_pipeline, render_project_sidebar
from mynovel.workflows.open_book import title_options_from_blueprint

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


def render_model_setup_page(
    db_path: Path,
    provider_config: ProviderConfig | None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    return _page(
        title=t("model.title", locale),
        active="model",
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
          <div class="split">
            {_select("genre", t("book.genre", locale), t("book.ai_choice", locale), GENRE_PRESETS)}
            {_select("audience", t("book.audience", locale), t("book.ai_choice", locale), AUDIENCE_PRESETS)}
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
          <p>{t("blueprint.genre", locale)}</p>
          <p>{t("blueprint.audience", locale)}</p>
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
        content_class="content-grid blueprint-layout",
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
    volume_plans: list[VolumePlan] | None = None,
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
        <div class="actions state-link">
          <a class="button secondary" href="/book/{book.id}/state">{t("trusted_state.open", locale)}</a>
          <a class="button secondary" href="/book/{book.id}/quality">{t("quality.open", locale)}</a>
          <a class="button secondary" href="/book/{book.id}/export.md">{t("export.markdown", locale)}</a>
          <a class="button secondary" href="/book/{book.id}/export.json">{t("export.json", locale)}</a>
        </div>
        {_render_foundation_board(canon, locale)}
        {_render_volume_plan_board(volume_plans or [])}
        {_render_chapter_table(chapters, locale)}
      </section>
      <aside class="right-panel">
        <h2>{t("dashboard.next_action", locale)}</h2>
        {_render_next_action(active_chapter, locale)}
        <h2>{t("batch.title", locale)}</h2>
        {_render_batch_action(book, active_chapter, locale)}
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


def render_trusted_state_page(
    book: Book,
    canon: Canon | None,
    chapters: list[Chapter],
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    book_id = book.id or 0
    main = f"""
      {_render_book_sidebar(book, chapters, locale)}
      <section class="main-panel canon-gate-main">
        <div class="panel-head">
          <div>
            <h1>开书定盘</h1>
            <p>{t("trusted_state.page_copy", locale)}</p>
          </div>
          <span class="status-pill pending">Canon 提案 · 待确认</span>
        </div>
        {render_canon_gate_main(canon)}
      </section>
      {render_canon_gate_aside(book_id, canon)}
"""
    return _page(
        title=t("trusted_state.title", locale),
        active="review",
        main=main,
        message=message,
        bottom=_render_production_pipeline(None, locale),
        locale=locale,
        eyebrow="开书定盘",
        content_class="content-grid canon-gate-layout",
    )


def render_chapter_review(
    book: Book,
    chapters: list[Chapter],
    chapter: Chapter,
    canon: Canon | None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    if chapter.status == ChapterStatus.RUNNING:
        main = f"""
      {_render_book_sidebar(book, chapters, locale)}
      {render_chapter_production_main(chapter)}
      {render_chapter_production_aside(chapter)}
"""
        return _page(
            title=chapter.title,
            active="create",
            main=main,
            message=message,
            bottom=_render_production_pipeline(chapter.status, locale),
            locale=locale,
            eyebrow="章节生产",
            content_class="content-grid production-layout",
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
    content_class: str = "content-grid",
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
    )


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
          <a class="button secondary" href="/provider-config">{t("model.configure", locale)}</a>
        </div>
        <h2>快速上手</h2>
        <div class="stack-list home-quickstart">
          <p>了解创作流程 <span>›</span></p>
          <p>创建第一个世界观 <span>›</span></p>
          <p>导入已有项目 <span>›</span></p>
        </div>
        <h2>{t("trusted_state.title", locale)}</h2>
        <p>{t("trusted_state.empty_hint", locale)}</p>
      </aside>
      <aside class="right-panel model-form hidden-model-form" id="model-form" aria-hidden="true">
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
        <div class="setup-card"><strong>{model_status}</strong><a class="button secondary" href="/provider-config">AI API 设置</a></div>
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
    proposals = _render_blueprint_proposal_cards(content, title_options, locale)
    proposal = render_structured_blueprint(content, locale, include_title_options=False)
    return f"""
      <section class="main-panel blueprint-main">
        <div class="panel-head">
          <div>
            <h1>{t("blueprint.review_title", locale)}</h1>
            <p>{t("blueprint.review_copy", locale)}</p>
          </div>
          <span class="status-pill pending">{t("trusted_state.not_written", locale)}</span>
        </div>
        <div class="proposal-grid">{proposals}</div>
        <div class="blueprint-detail-grid">{proposal}</div>
      </section>
      <aside class="right-panel blueprint-actions">
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


def _render_blueprint_proposal_cards(
    content: dict[str, Any],
    title_options: list[str],
    locale: str,
) -> str:
    if not title_options:
        return f"<section class='proposal-card'><h3>{t('blueprint.title_options', locale)}</h3><p>—</p></section>"
    labels = ["方案 A", "方案 B", "方案 C"]
    cards = []
    for index, title in enumerate(title_options[:3]):
        directions = content.get("chapter_directions")
        direction_items = directions if isinstance(directions, list) else []
        chapter_rows = "".join(
            f"<li>{_render_nested(item)}</li>" for item in direction_items[index : index + 3]
        )
        if not chapter_rows:
            chapter_rows = "<li>围绕核心冲突推进前 10 章承诺。</li>"
        cards.append(
            f"""
        <section class="proposal-card">
          <header><h3>{labels[index] if index < len(labels) else f"方案 {index + 1}"}</h3><span class="status-pill pending">候选中</span></header>
          <dl>
            <dt>{t("blueprint.title_options", locale)}</dt><dd>{html.escape(title)}</dd>
            <dt>{t("blueprint.central_conflict", locale)}</dt><dd>{_render_nested(content.get("central_conflict"))}</dd>
            <dt>{t("blueprint.protagonist", locale)}</dt><dd>{_render_nested(content.get("protagonist"))}</dd>
            <dt>{t("blueprint.world", locale)}</dt><dd>{_render_nested(content.get("world"))}</dd>
          </dl>
          <h3>{t("blueprint.chapter_directions", locale)}</h3>
          <ol>{chapter_rows}</ol>
        </section>
"""
        )
    return "".join(cards)


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
        ("卷级目标", plan.core_conflict),
        ("节奏曲线", "；".join(str(item) for item in plan.pacing_curve[:4])),
        ("爽点兑现", "；".join(str(item) for item in plan.payoff_distribution[:4])),
        ("关键转折", "；".join(str(item) for item in plan.key_turns[:4])),
        ("阶段承诺", "；".join(str(item) for item in plan.commitments[:4])),
    ]
    content = "".join(
        f"<p><strong>{html.escape(label)}</strong> {html.escape(str(value))}</p>"
        for label, value in rows
        if value
    )
    return f"<section class='data-card'><h3>{html.escape(plan.title)}</h3>{content}</section>"


def _render_trusted_state_sections(canon: Canon | None, locale: str) -> str:
    if canon is None:
        return f"<p>{t('trusted_state.missing', locale)}</p>"
    content = canon.content
    sections = [
        ("trusted_state.world_rules", content.get("world_rules", [])),
        ("trusted_state.characters", content.get("characters", [])),
        ("trusted_state.locations", content.get("locations", [])),
        ("trusted_state.relationships", content.get("relationships", [])),
        ("trusted_state.foreshadowing", content.get("foreshadowing", [])),
        ("trusted_state.chapter_summaries", content.get("chapter_summaries", [])),
        ("trusted_state.state_history", content.get("state_history", [])),
    ]
    return (
        "<div class='state-sections'>"
        + "".join(
            f"<section class='data-card'><h2>{t(label, locale)}</h2>{_render_value(value)}</section>"
            for label, value in sections
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


def _render_batch_action(book: Book, chapter: Chapter | None, locale: str) -> str:
    if book.status == BookStatus.PAUSED:
        return f"<p>{t('batch.paused', locale)}</p>"
    if chapter is None or book.id is None:
        return f"<p>{t('dashboard.all_done', locale)}</p>"
    return f"""
      <form method="post" action="/run-chapter-batch" class="compact-form">
        <input type="hidden" name="book_id" value="{book.id}">
        <label>{t("batch.limit", locale)}<input name="limit" type="number" min="1" max="10" value="5"></label>
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
    text = chapter.final_text or chapter.revised_text or chapter.draft_text
    edit_form = ""
    if chapter.status in {ChapterStatus.AWAITING_REVIEW, ChapterStatus.NEEDS_REVISION}:
        edit_form = f"""
      <form method="post" action="/edit-chapter-text" class="manual-edit">
        <input type="hidden" name="chapter_id" value="{chapter.id}">
        <label>{t("chapter.manual_text", locale)}<textarea name="manual_text">{html.escape(text)}</textarea></label>
        <label>{t("chapter.reviewer_note", locale)}<textarea name="reviewer_note" placeholder="{t("chapter.manual_note_placeholder", locale)}"></textarea></label>
        <button class="secondary" type="submit">{t("action.save_manual_edit", locale)}</button>
      </form>
"""
    return f"""
      <article class="chapter-text">{html.escape(text).replace(chr(10), "<br>")}</article>
      {edit_form}
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
    major_changes = _major_state_changes(chapter)
    canon_version = canon.version if canon else 0
    action = ""
    if chapter.status == ChapterStatus.AWAITING_REVIEW:
        major_confirmation = ""
        if major_changes:
            major_confirmation = f"""
            <p class="danger">{t("review.major_change_warning", locale)}</p>
            <label class="inline-check"><input name="allow_major_changes" type="checkbox" value="1">{t("review.confirm_major_change", locale)}</label>
"""
        action = f"""
          <div class="review-action-stack">
          <form method="post" action="/repair-chapter" class="compact-form action-form">
            <input type="hidden" name="chapter_id" value="{chapter.id}">
            <input type="hidden" name="reviewer_note" value="">
            <button class="secondary" type="submit">{t("action.repair_with_ai", locale)}</button>
          </form>
          <form method="post" action="/request-revision" class="compact-form action-form">
            <input type="hidden" name="chapter_id" value="{chapter.id}">
            <input type="hidden" name="reviewer_note" value="">
            <button class="secondary" type="submit">{t("action.return_for_revision", locale)}</button>
          </form>
          <form id="approve-form" method="post" action="/approve-chapter" class="compact-form action-form">
            <input type="hidden" name="chapter_id" value="{chapter.id}">
            <input type="hidden" name="reviewer_note" value="">
            {major_confirmation}
            <button type="submit">{t("action.accept_to_trusted_state", locale)}</button>
          </form>
          </div>
"""
    elif chapter.status == ChapterStatus.ACCEPTED:
        action = f"""
          {render_accepted_result(chapter)}
          <div class="actions">
            <a class="button" href="/chapter/{chapter.id}/export">{t("action.export_chapter", locale)}</a>
          </div>
"""
    return f"""
      {render_review_tabs()}
      <h2>{t("review.audit_issues", locale)}</h2>
      <ul class="review-list">{issue_rows}</ul>
      <h2>{t("review.state_delta", locale)}</h2>
      <p>{t("trusted_state.current_version", locale, version=canon_version)}</p>
      {f"<p class='danger'>{t('review.major_change_count', locale, count=len(major_changes))}</p>" if major_changes else ""}
      <ul class="review-list">{delta_rows}</ul>
      {action}
      {render_impact_scope(chapter)}
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
        "changes": "变化",
        "direction": "方向",
        "from": "起点",
        "title": "标题",
        "goal": "目标",
        "name": "名称",
        "hook": "钩子",
        "impact": "影响",
        "premise": "前提",
        "detail": "内容",
        "audience": "目标读者",
        "genre": "题材",
        "summary": "摘要",
        "target": "对象",
        "to": "终点",
        "type": "类型",
        "word_count": "字数",
    }
    return html.escape(labels.get(str(key), str(key)))


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
