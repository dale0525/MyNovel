from __future__ import annotations

import html

from mynovel.domain.models import OpenBookBlueprint
from mynovel.i18n import DEFAULT_LOCALE, t


def render_generating_blueprint(
    blueprint: OpenBookBlueprint,
    locale: str = DEFAULT_LOCALE,
) -> str:
    idea = html.escape(blueprint.idea)
    version = html.escape(str(blueprint.version))
    href = f"/blueprint/{blueprint.id or 0}"
    return f"""
      <section class="main-panel blueprint-main">
        <div class="panel-head">
          <div>
            <h1>{t("blueprint.generating_title", locale)}</h1>
            <p>{t("blueprint.generating_copy", locale)}</p>
          </div>
          <span class="status-pill pending">{t("blueprint.auto_refreshing", locale)}</span>
        </div>
        <ol class="setup-checklist">
          <li class="done"><span>✓</span><div><strong>{t("blueprint.step_idea_received", locale)}</strong><p>{idea}</p></div></li>
          <li class="done"><span>✓</span><div><strong>{t("blueprint.step_job_created", locale)}</strong><p>{t("blueprint.version", locale, version=version)}</p></div></li>
          <li><span>3</span><div><strong>{t("blueprint.step_model_running", locale)}</strong><p>{t("blueprint.step_model_running_copy", locale)}</p></div></li>
        </ol>
        <script>setTimeout(() => window.location.reload(), 3000)</script>
      </section>
      <aside class="right-panel blueprint-actions">
        <h2>{t("blueprint.generating_context", locale)}</h2>
        <div class="stack-list">
          <p>{t("blueprint.auto_refreshing_hint", locale)}</p>
          <p>{t("blueprint.generating_next", locale)}</p>
        </div>
        <div class="actions">
          <a class="button secondary" href="{href}">{t("blueprint.refresh_now", locale)}</a>
        </div>
      </aside>
"""
