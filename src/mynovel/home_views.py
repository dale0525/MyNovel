from __future__ import annotations

import html

from mynovel.domain.models import Book, BookStatus, BlueprintStatus, OpenBookBlueprint, ProviderConfig
from mynovel.i18n import DEFAULT_LOCALE, t


def render_empty_home(
    provider_config: ProviderConfig | None,
    blueprints: list[OpenBookBlueprint],
    configured: bool,
    locale: str = DEFAULT_LOCALE,
) -> str:
    status = t("model.ready", locale) if configured else t("model.not_ready", locale)
    blueprint_entry = _latest_blueprint_entry(blueprints, locale)
    recent_projects = (
        f'<div class="project-list">{blueprint_entry}</div>'
        if blueprint_entry
        else f'<div class="empty-box">{t("home.empty_recent", locale)}</div>'
    )
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
        {recent_projects}
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
        <div class="setup-card"><strong>{model_status}</strong><a class="button secondary" href="/provider-config">AI API 设置</a></div>
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
