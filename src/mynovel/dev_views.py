from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint, ProviderConfig
from mynovel.i18n import DEFAULT_LOCALE, t


def render_blueprint_page(
    db_path: Path,
    provider_config: ProviderConfig | None,
    blueprint: OpenBookBlueprint,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    escaped_message = html.escape(message) if message else ""
    db_label = html.escape(str(db_path))
    body = _render_blueprint_detail(blueprint, locale)
    retry_form = _render_retry_form(blueprint, locale)
    revision_form = _render_revision_form(blueprint, locale)
    config_status = (
        t("status.configured", locale)
        if _is_provider_config_complete(provider_config)
        else t("status.not_configured", locale)
    )

    return f"""<!doctype html>
<html lang="{locale}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{t("blueprint.title", locale, version=blueprint.version)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #eef2ed;
      --panel: #fbfcf8;
      --ink: #1e2a24;
      --muted: #65736b;
      --line: #d5ddd2;
      --accent: #356b55;
      --accent-ink: #ffffff;
      --warn: #7a5b21;
      --error: #8d352b;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}

    main {{
      width: min(1040px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0;
    }}

    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 24px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
    }}

    h1 {{ margin: 0 0 8px; font-size: 32px; line-height: 1.1; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    h3 {{ margin: 18px 0 8px; font-size: 15px; color: var(--muted); }}
    p {{ margin: 0; color: var(--muted); line-height: 1.6; }}

    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 20px;
    }}

    .db {{ color: var(--muted); font-size: 14px; text-align: right; }}
    .message {{ margin-bottom: 16px; color: var(--warn); font-size: 14px; }}
    .error {{ color: var(--error); }}
    .status {{
      display: inline-flex;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 13px;
      min-height: 28px;
      padding: 3px 10px;
      margin-bottom: 16px;
    }}

    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}

    a.button,
    button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: var(--accent-ink);
      cursor: pointer;
      font: inherit;
      font-weight: 650;
      padding: 9px 14px;
      text-decoration: none;
    }}

    a.secondary {{
      border: 1px solid var(--line);
      background: #ffffff;
      color: var(--ink);
    }}

    textarea {{
      width: 100%;
      min-height: 100px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      color: var(--ink);
      font: inherit;
      margin-top: 8px;
      padding: 9px 11px;
    }}

    ul {{ margin: 0; padding-left: 20px; }}
    li {{ margin: 5px 0; line-height: 1.55; }}
    dl {{ display: grid; grid-template-columns: minmax(120px, 180px) 1fr; gap: 10px 18px; }}
    dt {{ color: var(--muted); }}
    dd {{ margin: 0; line-height: 1.55; }}
    pre {{
      overflow: auto;
      max-height: 260px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f6f8f3;
      font-size: 13px;
      line-height: 1.55;
      padding: 14px;
      white-space: pre-wrap;
    }}

    @media (max-width: 720px) {{
      header {{ display: grid; }}
      .db {{ text-align: left; }}
      dl {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{t("blueprint.title", locale, version=blueprint.version)}</h1>
        <p>{html.escape(blueprint.idea)}</p>
      </div>
      <div class="db">{t("app.sqlite", locale)}<br>{db_label}<br>{config_status}</div>
    </header>

    {"<p class='message'>" + escaped_message + "</p>" if escaped_message else ""}

    <section>
      {body}
      {retry_form}
      {revision_form}
    </section>
  </main>
</body>
</html>
"""


def render_structured_blueprint(content: dict[str, Any], locale: str) -> str:
    if not content:
        return "<p></p>"
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
    rendered = []
    for label_key, value in sections:
        if value in (None, "", [], {}):
            continue
        rendered.append(f"<h3>{t(label_key, locale)}</h3>{_render_blueprint_value(value)}")
    return "\n".join(rendered)


def blueprint_status_label(status: BlueprintStatus | str, locale: str) -> str:
    status_value = status.value if isinstance(status, BlueprintStatus) else str(status)
    labels = {
        BlueprintStatus.PENDING.value: t("blueprint.pending", locale),
        BlueprintStatus.RUNNING.value: t("blueprint.running", locale),
        BlueprintStatus.SUCCEEDED.value: t("blueprint.succeeded", locale),
        BlueprintStatus.FAILED.value: t("blueprint.failed", locale),
    }
    return labels.get(status_value, status_value)


def _render_blueprint_detail(blueprint: OpenBookBlueprint, locale: str) -> str:
    status_label = blueprint_status_label(blueprint.status, locale)
    status_class = "status error" if blueprint.status == BlueprintStatus.FAILED else "status"
    if blueprint.status in {BlueprintStatus.PENDING, BlueprintStatus.RUNNING}:
        return f"""
          <p class="{status_class}">{status_label}</p>
          <p>{t("blueprint.running", locale)}</p>
          <div class="actions">
            <a class="button secondary" href="/blueprint/{blueprint.id}">{t("blueprint.refresh", locale)}</a>
          </div>
"""

    if blueprint.status == BlueprintStatus.FAILED:
        error_message = html.escape(blueprint.error_message or blueprint.parse_error or "")
        raw_response = html.escape(blueprint.raw_response or "")
        raw_block = (
            f"<h3>{t('blueprint.raw_response', locale)}</h3><pre>{raw_response}</pre>"
            if raw_response
            else ""
        )
        return f"""
          <p class="{status_class}">{t("blueprint.failed", locale)}</p>
          <p class="error">{error_message}</p>
          {raw_block}
"""

    return f"""
      <p class="{status_class}">{status_label}</p>
      {render_structured_blueprint(blueprint.content, locale)}
"""


def _render_retry_form(blueprint: OpenBookBlueprint, locale: str) -> str:
    if blueprint.status != BlueprintStatus.FAILED:
        return ""
    return f"""
      <form method="post" action="/retry-blueprint" class="actions">
        <input type="hidden" name="blueprint_id" value="{blueprint.id}">
        <button type="submit">{t("blueprint.retry", locale)}</button>
      </form>
"""


def _render_revision_form(blueprint: OpenBookBlueprint, locale: str) -> str:
    if blueprint.status != BlueprintStatus.SUCCEEDED:
        return ""
    return f"""
      <form method="post" action="/revise-blueprint">
        <label>
          {t("blueprint.revision_notes", locale)}
          <textarea name="revision_notes" required
            placeholder="主角更疯一点，节奏更爽文"></textarea>
        </label>
        <div class="actions">
          <button type="submit">{t("blueprint.revise", locale)}</button>
          <a class="button secondary" href="/">{t("app.title", locale)}</a>
        </div>
      </form>
"""


def _render_blueprint_value(value: Any) -> str:
    if isinstance(value, list):
        items = "".join(f"<li>{_render_nested_value(item)}</li>" for item in value)
        return f"<ul>{items}</ul>"
    if isinstance(value, dict):
        return _render_blueprint_mapping(value)
    return f"<p>{html.escape(str(value))}</p>"


def _render_nested_value(value: Any) -> str:
    if isinstance(value, list):
        items = "".join(f"<li>{_render_nested_value(item)}</li>" for item in value)
        return f"<ul>{items}</ul>"
    if isinstance(value, dict):
        return _render_blueprint_mapping(value)
    return html.escape(str(value))


def _render_blueprint_mapping(value: dict[Any, Any]) -> str:
    rows = "".join(
        f"<dt>{html.escape(str(key))}</dt><dd>{_render_nested_value(item)}</dd>"
        for key, item in value.items()
    )
    return f"<dl>{rows}</dl>"


def _is_provider_config_complete(provider_config: ProviderConfig | None) -> bool:
    return bool(
        provider_config
        and provider_config.llm_base_url.strip()
        and provider_config.llm_model.strip()
        and provider_config.resolved_embedding_base_url().strip()
        and provider_config.embedding_model.strip()
    )
