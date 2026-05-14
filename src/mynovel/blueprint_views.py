from __future__ import annotations

import html

from mynovel.domain.models import OpenBookBlueprint
from mynovel.i18n import DEFAULT_LOCALE, t


def render_blueprint_sidebar(
    blueprint: OpenBookBlueprint,
    locale: str = DEFAULT_LOCALE,
) -> str:
    current_step = "02" if blueprint.status.value in {"pending", "running"} else "02"
    current_label = "生成中" if blueprint.status.value in {"pending", "running"} else "候选选择中"
    steps = [
        ("01", "书籍设定", "已完成", True),
        ("02", "开书方案", current_label, True),
        ("03", "世界观搭建", "待开始", False),
        ("04", "角色设计", "待开始", False),
        ("05", "前 10 章节奏", "待开始", False),
        ("06", "可信设定定盘", "待开始", False),
    ]
    rows = "".join(
        _blueprint_step(number, label, state, active=(number == current_step), done=done)
        for number, label, state, done in steps
    )
    return f"""
      <aside class="project-context blueprint-context">
        <div class="project-identity">
          <div class="project-cover forest-cover" aria-hidden="true"></div>
          <div>
            <h2>{_blueprint_title(blueprint)}</h2>
            <p>奇幻 · 候选方向</p>
            <p>120,000 字</p>
            <span class="status-pill pending">尚未写入可信设定</span>
          </div>
        </div>
        <a class="button secondary project-overview" href="/">项目概览</a>
        <h3>开书流程（共 6 步）</h3>
        <div class="blueprint-step-list">{rows}</div>
        <a class="button secondary new-chapter" href="/books/new">‹ 返回书籍设定</a>
      </aside>
"""


def render_generating_blueprint(
    blueprint: OpenBookBlueprint,
    locale: str = DEFAULT_LOCALE,
    model_name: str | None = None,
) -> str:
    idea = html.escape(blueprint.idea)
    version = html.escape(str(blueprint.version))
    href = f"/blueprint/{blueprint.id or 0}"
    model_label = html.escape(model_name or "当前对话模型")
    return f"""
      <section class="main-panel blueprint-main">
        <div class="panel-head">
          <div>
            <h1>{t("blueprint.generating_title", locale)}</h1>
            <p>{t("blueprint.generating_copy", locale)}</p>
          </div>
          <span class="status-pill pending">{t("blueprint.auto_refreshing", locale)}</span>
        </div>
        <div class="blueprint-generating-timeline">
          <article class="done"><span>✓</span><div><strong>{t("blueprint.step_idea_received", locale)}</strong><p>{idea}</p></div><time>14:32:18</time></article>
          <article class="done"><span>✓</span><div><strong>{t("blueprint.step_job_created", locale)}</strong><p>{t("blueprint.version", locale, version=version)}</p></div><time>14:32:19</time></article>
          <article class="current"><span>●</span><div><strong>{t("blueprint.step_model_running", locale)}</strong><p>{t("blueprint.step_model_running_copy", locale)}</p></div><b class="loading-wave" aria-hidden="true">••••••••••••••</b></article>
          <article><span>○</span><div><strong>结构化校验</strong><p>校验输出结构、字段完整性与合规性。</p></div></article>
        </div>
        <script>setTimeout(() => window.location.reload(), 3000)</script>
      </section>
      <aside class="right-panel blueprint-actions">
        <h2>{t("blueprint.generating_context", locale)}</h2>
        <div class="generation-task-list">
          <p><strong>运行记录</strong><span>记录模型和提示词版本</span></p>
          <p><strong>模型</strong><span>{model_label}</span></p>
          <p><strong>提示词编号</strong><span>open_book_v0.1.0</span></p>
          <p><strong>自动刷新</strong><span>{t("blueprint.auto_refreshing_hint", locale)}</span></p>
          <p><strong>完成后动作</strong><span>{t("blueprint.generating_next", locale)}</span></p>
        </div>
        <div class="actions">
          <a class="button secondary" href="{href}">{t("blueprint.refresh_now", locale)}</a>
        </div>
      </aside>
"""


def _blueprint_step(number: str, label: str, state: str, *, active: bool, done: bool) -> str:
    state_class = " active" if active else " done" if done else ""
    icon = "✓" if done and not active else number
    return (
        f'<div class="blueprint-step{state_class}"><span>{html.escape(icon)}</span>'
        f"<strong>{html.escape(number)}　{html.escape(label)}</strong><em>{html.escape(state)}</em></div>"
    )


def _blueprint_title(blueprint: OpenBookBlueprint) -> str:
    options = blueprint.content.get("title_options") if blueprint.content else None
    if isinstance(options, list) and options:
        return html.escape(str(options[0]))
    return "未定名新书"
