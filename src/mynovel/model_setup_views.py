from __future__ import annotations

import html
from pathlib import Path

from mynovel.domain.models import ProviderConfig
from mynovel.i18n import DEFAULT_LOCALE
from mynovel.provider_config_validation import ProviderValidationReport


def render_model_setup_content(
    db_path: Path,
    provider_config: ProviderConfig | None,
    locale: str = DEFAULT_LOCALE,
    validation_report: ProviderValidationReport | None = None,
) -> str:
    _ = locale
    config = provider_config or ProviderConfig(
        llm_base_url="",
        llm_model="",
        embedding_use_llm_credentials=True,
        embedding_base_url="",
        embedding_model="",
        rerank_use_llm_credentials=True,
    )
    llm_base_ready = bool(config.llm_base_url.strip())
    llm_model_ready = bool(config.llm_model.strip())
    key_ready = bool(config.llm_api_key)
    llm_ready = bool(llm_base_ready and key_ready and llm_model_ready)
    embedding_model_ready = bool(config.embedding_model.strip())
    embedding_endpoint_ready = bool(config.resolved_embedding_base_url().strip())
    embedding_key_ready = bool(config.resolved_embedding_api_key())
    embedding_ready = bool(embedding_model_ready and embedding_endpoint_ready and embedding_key_ready)
    rerank_model_ready = bool(config.rerank_model and config.rerank_model.strip())
    rerank_endpoint_ready = bool((config.resolved_rerank_base_url() or "").strip())
    rerank_key_ready = bool(config.resolved_rerank_api_key())
    rerank_ready = bool(rerank_model_ready and rerank_endpoint_ready and rerank_key_ready)

    return f"""
      <aside class="setup-guide">
        {_setup_guide_card("1", "接口类型说明", "OpenAI-compatible 是唯一接口类型，兼容 OpenAI 接口协议的服务商均可使用。")}
        {_setup_guide_card("2", "测试通过后解锁开书", "对话、检索、重排三个模型都测试通过后，将解锁“开始创作第一本书”。")}
        {_setup_guide_card("3", "密钥本地保存", "访问密钥仅保存在本机，不会上传到任何服务器。")}
      </aside>
      <section class="model-config-panel">
        <div class="panel-head">
          <div>
            <h1>模型配置</h1>
            <h2>连接你的 AI 模型 <span class="info-dot">?</span></h2>
            <p>填写并保存时会自动测试对话、检索和重排模型；任意一个失败都不会保存。</p>
          </div>
        </div>
        <form method="post" action="/provider-config" class="model-config-form">
          <div class="model-field">
            <label>服务类型</label>
            <div class="select-shell"><span class="check-dot">✓</span><span>OpenAI-compatible</span><span>⌄</span></div>
            <p>目前仅支持 OpenAI-compatible 接口（包括 OpenAI 官方与兼容服务）</p>
          </div>
          <section class="model-credential-section">
            <header>
              <h3>对话模型接口</h3>
              <p>用于开书、章节生成、修订和审计。</p>
            </header>
          {_input("llm_base_url", "接口地址", "https://api.example.com/v1", _field(config.llm_base_url), True, "✓" if llm_base_ready else "")}
          {_input("llm_api_key", "访问密钥", "", _field(config.llm_api_key), True, "✓" if key_ready else "", "password")}
          {_input("llm_model", "对话模型", "gpt-4o-mini", _field(config.llm_model), True, "✓" if llm_model_ready else "")}
          </section>
          <div class="model-divider"></div>
          <section class="model-credential-section">
            <header>
              <h3>检索模型接口</h3>
              <p>用于记忆召回和章节上下文检索。</p>
            </header>
              {_input("embedding_model", "检索模型", "bge-m3", _field(config.embedding_model), True, "✓" if embedding_model_ready else "")}
              {_credential_checkbox("embedding_use_llm_credentials", "检索模型使用和对话模型一样的接口与密钥", config.embedding_use_llm_credentials)}
              {_input("embedding_base_url", "检索接口地址", "https://api.example.com/v1", _field(config.embedding_base_url), not config.embedding_use_llm_credentials)}
              {_input("embedding_api_key", "检索访问密钥", "", _field(config.embedding_api_key), not config.embedding_use_llm_credentials, "", "password")}
          </section>
          <div class="model-divider"></div>
          <section class="model-credential-section">
            <header>
              <h3>重排模型接口</h3>
              <p>用于对召回结果排序，提升长篇上下文准确度。</p>
            </header>
              {_input("rerank_model", "重排模型", "bge-reranker-v2-m3", _field(config.rerank_model), True, "✓" if rerank_model_ready else "")}
              {_credential_checkbox("rerank_use_llm_credentials", "重排模型使用和对话模型一样的接口与密钥", config.rerank_use_llm_credentials)}
              {_input("rerank_base_url", "重排接口地址", "https://api.example.com/v1", _field(config.rerank_base_url), not config.rerank_use_llm_credentials)}
              {_input("rerank_api_key", "重排访问密钥", "", _field(config.rerank_api_key), not config.rerank_use_llm_credentials, "", "password")}
          </section>
          <div class="model-actions">
            <button type="submit">保存并测试模型</button>
          </div>
        </form>
      </section>
      <aside class="right-panel setup-aside">
        {_render_connection_checks(validation_report)}
        <section>
          <h2>准备创建书籍</h2>
          <p>完成以下设置后，即可开始创建你的第一本书。</p>
          <ol class="setup-checklist">
            {_check_item("选择 OpenAI-compatible 服务类型", "仅支持 OpenAI-compatible 接口", True)}
            {_check_item("配置接口地址", "访问正常", llm_ready)}
            {_check_item("保存访问密钥", "已安全保存在本机", key_ready)}
            {_check_item("选择对话模型", config.llm_model or "待填写", bool(config.llm_model))}
            {_check_item("配置检索模型", "用于记忆与检索，是当前流程的必填项", embedding_ready)}
            {_check_item("配置重排模型", "用于重排检索结果，是当前流程的必填项", rerank_ready)}
          </ol>
        </section>
        <section class="local-database-card">
          <h2>本地数据库</h2>
          <p>所有设置与内容仅保存在本机数据库中，不上传、不共享，完全由你掌控。</p>
          <ul>
            <li>模型配置仅存储在本机加密数据库</li>
            <li>书籍内容、审计与可信设定只保存在本地</li>
            <li>可以随时备份或迁移到其他设备</li>
          </ul>
          <a class="button secondary" href="/">查看数据位置</a>
          <p class="db-path">{html.escape(str(db_path))}</p>
        </section>
      </aside>
"""


def _setup_guide_card(number: str, title: str, copy: str) -> str:
    return (
        '<section class="setup-guide-card">'
        f"<span>{html.escape(number)}</span><h2>{html.escape(title)}</h2>"
        f"<p>{html.escape(copy)}</p></section>"
    )


def _input(
    name: str,
    label: str,
    placeholder: str = "",
    value: str = "",
    required: bool = False,
    suffix: str = "",
    input_type: str = "text",
) -> str:
    suffix_html = f"<span class='field-status'>{html.escape(suffix)}</span>" if suffix else ""
    return (
        f'<div class="model-field annotated-model-field"><label for="{name}">{label}</label><div class="input-shell">'
        f'<input id="{name}" name="{name}" type="{input_type}" value="{value}" '
        f'placeholder="{html.escape(placeholder, quote=True)}"{" required" if required else ""}>'
        f"{suffix_html}</div></div>"
    )


def _credential_checkbox(name: str, label: str, checked: bool) -> str:
    checked_attr = " checked" if checked else ""
    return (
        f'<input type="hidden" name="{name}" value="0">'
        f'<label class="inline-check model-check">'
        f'<input name="{name}" type="checkbox" value="1"{checked_attr}>'
        f"{html.escape(label)}</label>"
    )


def _render_connection_checks(validation_report: ProviderValidationReport | None) -> str:
    if validation_report is None:
        rows = "".join(
            _connection_check_item(label, "untested", "保存时自动测试")
            for label in ("对话模型", "检索模型", "重排模型")
        )
    else:
        rows = "".join(
            _connection_check_item(result.label, result.status, result.message)
            for result in validation_report.results
        )
    return f"""
        <section class="connection-checks">
          <h2>连接检查</h2>
          <p>保存时会测试三个模型；已通过且配置未变化的模型会沿用上次通过结果。</p>
          <ol class="setup-checklist connection-checklist">{rows}</ol>
        </section>
"""


def _connection_check_item(label: str, status: str, message: str) -> str:
    status_labels = {
        "passed": "通过",
        "failed": "失败",
        "skipped": "沿用上次通过结果",
        "untested": "未测试",
    }
    state = {
        "passed": "done",
        "failed": "todo",
        "skipped": "done",
        "untested": "todo",
    }.get(status, "todo")
    icon = "✓" if status in {"passed", "skipped"} else "○"
    status_label = status_labels.get(status, status)
    return (
        f'<li class="{state}"><span>{icon}</span><div><strong>{html.escape(label)}'
        f" · {html.escape(status_label)}</strong><p>{html.escape(message)}</p></div></li>"
    )


def _field(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def _check_item(title: str, subtitle: str, done: bool, optional: bool = False) -> str:
    state = "done" if done else "optional" if optional else "todo"
    icon = "✓" if done else "○"
    return (
        f'<li class="{state}"><span>{icon}</span><div><strong>{html.escape(title)}</strong>'
        f"<p>{html.escape(subtitle)}</p></div></li>"
    )
