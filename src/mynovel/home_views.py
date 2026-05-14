from __future__ import annotations

import html

from mynovel.domain.models import (
    Book,
    BookStatus,
    BlueprintStatus,
    OpenBookBlueprint,
    ProviderConfig,
)
from mynovel.i18n import DEFAULT_LOCALE, t


def render_empty_home(
    provider_config: ProviderConfig | None,
    blueprints: list[OpenBookBlueprint],
    configured: bool,
    locale: str = DEFAULT_LOCALE,
) -> str:
    status = t("model.ready", locale) if configured else t("model.not_ready", locale)
    status_hint = t("model.ready_hint", locale) if configured else t("model.not_ready_hint", locale)
    blueprint_entry = _latest_blueprint_entry(blueprints, locale)
    recent_body = (
        f'<div class="project-list">{blueprint_entry}</div>'
        if blueprint_entry
        else (
            '<div class="recent-empty">'
            '<span class="empty-file-icon" aria-hidden="true">▤</span>'
            f"<p>{t('home.empty_recent', locale)}</p>"
            "</div>"
        )
    )
    return f"""
      <section class="first-launch-hero">
        <div class="empty-book-illustration" aria-hidden="true">{_book_icon()}</div>
        <h1>{t("home.empty_title", locale)}</h1>
        <p>{t("home.empty_copy", locale)}</p>
        <p>{t("home.local_copy", locale)}</p>
        <div class="launch-actions">
          <a class="button launch-primary" href="/books/new">
            <span aria-hidden="true">＋</span>{t("home.create_first", locale)}
          </a>
          <a class="button secondary launch-secondary" href="/books/import">
            <span aria-hidden="true">⇧</span>{t("home.import_project", locale)}
          </a>
        </div>
      </section>
      <aside class="first-launch-aside">
        <section class="launch-card recent-projects-card">
          <header>
            <h2>{t("home.recent_projects", locale)}</h2>
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
        <section class="launch-card quickstart-card">
          <h2>快速上手</h2>
          <div class="quickstart-list">
            {_quickstart_item("▤", "了解创作流程", "从开书到写入可信设定的完整流程。", "#launch-pipeline")}
            {_quickstart_item("▣", "创建第一个世界观", "设定世界、规则与背景。", "/books/new")}
            {_quickstart_item("⇧", "导入已有项目", "从其他格式导入你的作品。", "/books/import")}
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
    rows = "".join(
        f"<a class='project-row' href='/book/{book.id}'><strong>{html.escape(book.title)}</strong>"
        f"<span>{_book_status_label(book.status, locale)}</span></a>"
        for book in books
    )
    blueprint_entry = _latest_blueprint_entry(blueprints, locale)
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
        <div class="project-list">{rows}{blueprint_entry}</div>
        <div class="setup-card"><strong>{model_status}</strong><a class="button secondary" href="/provider-config">模型接口设置</a></div>
      </section>
"""


def _latest_blueprint_entry(blueprints: list[OpenBookBlueprint], locale: str) -> str:
    if not blueprints:
        return ""
    latest = blueprints[0]
    return (
        f"<a class='project-row' href='/blueprint/{latest.id}'>"
        f"<strong>{t('blueprint.review_title', locale)}</strong>"
        f"<span>{_blueprint_status_label(latest.status, locale)}</span></a>"
    )


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
