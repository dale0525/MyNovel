from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime

from mynovel.domain.models import (
    Book,
    BookStatus,
    BlueprintStatus,
    OpenBookBlueprint,
    ProviderConfig,
)
from mynovel.i18n import DEFAULT_LOCALE, t


@dataclass(frozen=True)
class HomeRecentResult:
    title: str
    status: str
    href: str
    sort_key: datetime


def render_empty_home(
    provider_config: ProviderConfig | None,
    blueprints: list[OpenBookBlueprint],
    configured: bool,
    locale: str = DEFAULT_LOCALE,
) -> str:
    status = t("model.ready", locale) if configured else t("model.not_ready", locale)
    status_hint = t("model.ready_hint", locale) if configured else t("model.not_ready_hint", locale)
    recent_results = _collect_recent_results([], blueprints, locale)
    recent_body = _render_recent_timeline(recent_results, locale)
    return f"""
      <section class="main-panel current-focus-card first-launch-hero">
        <div class="empty-book-illustration" aria-hidden="true">{_book_icon()}</div>
        <p class="section-kicker">{t("home.focus_kicker", locale)}</p>
        <h1>{t("home.empty_title", locale)}</h1>
        <p>{t("home.empty_copy", locale)}</p>
        <p>{t("home.empty_followup", locale)}</p>
        <div class="focus-checklist">
          <p><strong>{t("home.focus_question", locale)}</strong></p>
          <p>{t("home.empty_focus_answer", locale)}</p>
        </div>
        <div class="launch-actions">
          <a class="button launch-primary" href="/books/new">
            <span aria-hidden="true">＋</span>{t("home.create_first", locale)}
          </a>
          <a class="button secondary launch-secondary" href="/books/import">
            <span aria-hidden="true">⇧</span>{t("home.import_project", locale)}
          </a>
        </div>
        <p>{t("home.local_copy", locale)}</p>
      </section>
      <aside class="right-panel ai-result-timeline first-launch-aside">
        <section class="launch-card timeline-section">
          <header>
            <h2>{t("home.recent_results", locale)}</h2>
            <a class="button secondary compact-button" href="/books/import">{t("home.open_project", locale)}</a>
          </header>
          {recent_body}
        </section>
        <section class="launch-card model-status-card">
          <h2>{t("model.status", locale)}</h2>
          <div class="model-ready-row">
            <span class="warn-icon" aria-hidden="true">△</span>
            <div>
              <strong>{status}</strong>
              <p>{status_hint}</p>
            </div>
            <a class="button secondary compact-button" href="/provider-config">{t("model.configure", locale)}</a>
          </div>
        </section>
      </aside>
      <aside class="right-panel model-form hidden-model-form" id="model-form" aria-hidden="true">
        <h2>{t("model.title", locale)}</h2>
        {_render_provider_form(provider_config, locale)}
      </aside>
"""


def render_project_home(
    books: list[Book],
    blueprints: list[OpenBookBlueprint],
    configured: bool,
    locale: str = DEFAULT_LOCALE,
) -> str:
    model_status = t("model.ready", locale) if configured else t("model.not_ready", locale)
    recent_results = _collect_recent_results(books, blueprints, locale)
    recent_body = _render_recent_timeline(recent_results, locale)
    return f"""
      <section class="main-panel current-focus-card">
        <div class="panel-head">
          <div>
            <p class="section-kicker">{t("home.focus_kicker", locale)}</p>
            <h1>{t("home.workspace_title", locale)}</h1>
            <p>{t("home.workspace_copy", locale)}</p>
          </div>
          <a class="button" href="/review">{t("home.enter_current_task", locale)}</a>
        </div>
        <div class="focus-checklist">
          <p><strong>{t("home.focus_question", locale)}</strong></p>
          <p>{t("home.focus_answer", locale)}</p>
          <p><strong>{t("home.recent_result_label", locale)}</strong></p>
          <p>{_recent_result_summary(recent_results, locale)}</p>
        </div>
        <div class="setup-card"><strong>{model_status}</strong><a class="button secondary" href="/provider-config">{t("home.settings_link", locale)}</a></div>
      </section>
      <aside class="right-panel ai-result-timeline">
        <h2>{t("home.recent_results", locale)}</h2>
        {recent_body}
      </aside>
"""


def _collect_recent_results(
    books: list[Book], blueprints: list[OpenBookBlueprint], locale: str
) -> list[HomeRecentResult]:
    results: list[HomeRecentResult] = []
    if blueprints:
        results.extend(
            HomeRecentResult(
                title=t("blueprint.review_title", locale),
                status=_blueprint_status_label(blueprint.status, locale),
                href=f"/blueprint/{blueprint.id}",
                sort_key=_blueprint_result_time(blueprint),
            )
            for blueprint in blueprints
        )
    results.extend(
        HomeRecentResult(
            title=book.title,
            status=_book_status_label(book.status, locale),
            href=f"/book/{book.id}",
            sort_key=book.updated_at,
        )
        for book in books
    )
    return sorted(results, key=lambda item: item.sort_key, reverse=True)


def _render_recent_timeline(results: list[HomeRecentResult], locale: str) -> str:
    if not results:
        return (
            '<div class="recent-empty">'
            '<span class="empty-file-icon" aria-hidden="true">▤</span>'
            f"<p>{t('home.timeline_empty', locale)}</p>"
            "</div>"
        )
    rows = "".join(
        f"<a class='timeline-row' href='{html.escape(item.href, quote=True)}'>"
        f"<strong>{html.escape(item.title)}</strong>"
        f"<span>{html.escape(item.status)}</span></a>"
        for item in results
    )
    return f"<div class='timeline-stack'>{rows}</div>"


def _recent_result_summary(results: list[HomeRecentResult], locale: str) -> str:
    if not results:
        return t("home.timeline_empty", locale)
    current = results[0]
    return f"{html.escape(current.title)} · {html.escape(current.status)}"


def _blueprint_result_time(blueprint: OpenBookBlueprint) -> datetime:
    return blueprint.finished_at or blueprint.started_at or blueprint.created_at


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
        {_input("llm_base_url", t("provider.llm_base_url", locale), t("provider.llm_base_url_placeholder", locale), _field(config.llm_base_url), True)}
        {_input("llm_api_key", t("provider.llm_api_key", locale), "", _field(config.llm_api_key), True, "password")}
        {_input("llm_model", t("provider.llm_model", locale), t("provider.llm_model_placeholder", locale), _field(config.llm_model), True)}
        {_input("embedding_model", t("provider.embedding_model", locale), t("provider.embedding_model_placeholder", locale), _field(config.embedding_model), True)}
        <label class="inline-check"><input name="embedding_use_llm_credentials" type="checkbox" value="1"{embedding_checked}>{t("provider.embedding_use_llm", locale)}</label>
        {_input("embedding_base_url", t("provider.embedding_base_url", locale), t("provider.embedding_base_url_placeholder", locale), _field(config.embedding_base_url))}
        {_input("embedding_api_key", t("provider.embedding_api_key", locale), "", _field(config.embedding_api_key), False, "password")}
        {_input("rerank_model", t("provider.rerank_model", locale), "填写重排模型名称", _field(config.rerank_model), True)}
        <label class="inline-check"><input name="rerank_use_llm_credentials" type="checkbox" value="1"{rerank_checked}>{t("provider.rerank_use_llm", locale)}</label>
        {_input("rerank_base_url", t("provider.rerank_base_url", locale), t("provider.optional_placeholder", locale), _field(config.rerank_base_url))}
        {_input("rerank_api_key", t("provider.rerank_api_key", locale), "", _field(config.rerank_api_key), False, "password")}
        <button type="submit">{t("provider.save", locale)}</button>
      </form>
"""


def _book_status_label(status: BookStatus | str, locale: str) -> str:
    value = status.value if isinstance(status, BookStatus) else str(status)
    return {
        BookStatus.DRAFT.value: t("book.status_draft", locale),
        BookStatus.CANON_LOCKED.value: t("book.status_locked", locale),
        BookStatus.PRODUCING.value: t("book.status_producing", locale),
        BookStatus.PAUSED.value: t("book.status_paused", locale),
    }.get(value, value)


def _blueprint_status_label(status: BlueprintStatus | str, locale: str) -> str:
    value = status.value if isinstance(status, BlueprintStatus) else str(status)
    labels = {
        BlueprintStatus.PENDING.value: t("blueprint.pending", locale),
        BlueprintStatus.RUNNING.value: t("blueprint.running_short", locale),
        BlueprintStatus.SUCCEEDED.value: t("blueprint.succeeded", locale),
        BlueprintStatus.FAILED.value: t("blueprint.failed", locale),
    }
    return labels.get(value, value)


def _quickstart_item(icon: str, title: str, copy: str, href: str) -> str:
    return (
        f'<a class="quickstart-row" href="{html.escape(href, quote=True)}">'
        f'<span class="quickstart-icon" aria-hidden="true">{html.escape(icon)}</span>'
        "<span>"
        f"<strong>{html.escape(title)}</strong>"
        f"<em>{html.escape(copy)}</em>"
        "</span>"
        '<b aria-hidden="true">›</b>'
        "</a>"
    )


def _book_icon() -> str:
    return """
      <svg viewBox="0 0 96 72" role="img" focusable="false">
        <path d="M47 63c-9-7-21-10-35-8V9c14-2 26 1 35 8v46Z" fill="none" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/>
        <path d="M49 63c9-7 21-10 35-8V9c-14-2-26 1-35 8v46Z" fill="none" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/>
        <path d="M48 18v45" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
        <path d="M61 35c-8 2-11 7-11 15 8-2 11-7 11-15Z" fill="currentColor" opacity=".28"/>
        <path d="M50 50c-4-7-9-11-16-12 1 8 6 12 16 12Z" fill="currentColor" opacity=".18"/>
      </svg>
"""


def _input(
    name: str,
    label: str,
    placeholder: str,
    value: str = "",
    required: bool = False,
    input_type: str = "text",
) -> str:
    required_attr = " required" if required else ""
    return (
        f'<label>{label}<input name="{name}" type="{input_type}" value="{value}" '
        f'placeholder="{placeholder}"{required_attr}></label>'
    )


def _field(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)
