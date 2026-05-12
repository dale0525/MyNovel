from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from mynovel.domain.models import Book, BookStatus, Chapter, ChapterStatus
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.word_targets import book_target_word_count, format_word_count


@dataclass(frozen=True)
class PipelineStep:
    key: str
    label: str
    state: str = "pending"
    note: str = "待开始"
    icon: str = "○"


@dataclass(frozen=True)
class ProjectNavLinks:
    docs: str
    characters: str
    world: str
    analysis: str


def render_app_page(
    *,
    title: str,
    active: str,
    main: str,
    bottom: str = "",
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
    db_path: Path | None = None,
    eyebrow: str | None = None,
    content_class: str = "content-grid",
    nav_book_id: int | None = None,
) -> str:
    nav_links = project_nav_links(nav_book_id)
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
  <style>{app_css()}</style>
</head>
<body>
  <div class="app-shell">
    <nav class="rail" aria-label="主导航">
      <a class="brand" href="/" aria-label="MyNovel"><span class="brand-mark">◇</span><strong>MyNovel</strong></a>
      <div class="nav-stack">
        {render_nav_item("/", t("nav.workspace", locale), "⌂", active == "workspace")}
        {render_nav_item("/books/new", t("nav.create", locale), "▣", active == "create")}
        {render_nav_item(nav_links.docs, t("nav.docs", locale), "□", active == "docs")}
        {render_nav_item(nav_links.characters, "角色", "♙", active == "characters")}
        {render_nav_item(nav_links.world, "世界观", "◎", active == "world")}
        {render_nav_item(nav_links.analysis, "分析", "▥", active == "analysis")}
        {render_nav_item("/review", t("nav.review", locale), "✓", active == "review")}
      </div>
      <div class="nav-bottom">
        {render_nav_item("/provider-config", "模型配置", "◈", active == "model")}
        {render_nav_item("/updates", t("nav.settings", locale), "⚙", active == "settings")}
      </div>
    </nav>
    <main class="workspace">
      <header class="topbar">
        <div><span class="eyebrow">{html.escape(eyebrow or t("app.product_mode", locale))}</span></div>
        <div class="top-actions">
          <a href="/">查看日志</a>
          <span aria-hidden="true">◌</span>
          <a href="/provider-config">AI API 设置</a>
          <span aria-hidden="true">◌</span>
          <a href="/updates">设置</a>
          {db_hint}
          <span>{t("app.local_first", locale)}</span>
        </div>
      </header>
      {f"<p class='notice'>{html.escape(message)}</p>" if message else ""}
      <div class="{html.escape(content_class, quote=True)}">{main}</div>
      {bottom}
    </main>
  </div>
</body>
</html>
"""


def project_nav_links(book_id: int | None) -> ProjectNavLinks:
    if book_id is None:
        return ProjectNavLinks(docs="/", characters="/review", world="/review", analysis="/review")
    return ProjectNavLinks(
        docs=f"/book/{book_id}",
        characters=f"/book/{book_id}/state#characters",
        world=f"/book/{book_id}/state#world",
        analysis=f"/book/{book_id}/quality",
    )


def render_nav_item(href: str, label: str, icon: str, active: bool) -> str:
    active_class = " active" if active else ""
    return (
        f'<a class="nav-item{active_class}" href="{html.escape(href, quote=True)}">'
        f'<span class="nav-icon" aria-hidden="true">{html.escape(icon)}</span>'
        f"<span>{html.escape(label)}</span></a>"
    )


def render_project_sidebar(
    book: Book,
    chapters: list[Chapter],
    *,
    active_chapter_id: int | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    title = html.escape(book.title)
    initials = html.escape((book.title[:1] or "书").upper())
    rows = "".join(
        _chapter_link(chapter, active_chapter_id, locale)
        for chapter in sorted(chapters, key=lambda item: item.number)
    )
    if not rows:
        rows = '<p class="muted">暂无章节。</p>'
    return f"""
      <aside class="project-context">
        <div class="project-identity">
          <div class="project-cover" aria-hidden="true">{initials}</div>
          <div>
            <h2>{title}</h2>
            <p>{html.escape(book.genre)} · {html.escape(book.audience)}</p>
            <p>{html.escape(format_word_count(book_target_word_count(book)))}</p>
            <span class="status-pill trusted">{_book_status_label(book.status)}</span>
          </div>
        </div>
        <a class="button secondary project-overview" href="/book/{book.id or 0}">项目概览</a>
        <h3>章节队列</h3>
        <div class="chapter-list">{rows}</div>
        <a class="button secondary new-chapter" href="/books/new">＋ 新建章节</a>
      </aside>
"""


def render_pipeline(steps: list[PipelineStep]) -> str:
    items = []
    for index, step in enumerate(steps):
        if index:
            items.append('<span class="pipeline-connector" aria-hidden="true"></span>')
        aria_current = ' aria-current="step"' if step.state == "current" else ""
        current_note = "当前阶段" if step.state == "current" else html.escape(step.note)
        items.append(
            f'<li class="pipeline-step {html.escape(step.state)}"{aria_current}>'
            f'<span class="pipeline-icon" aria-hidden="true">{html.escape(step.icon)}</span>'
            f"<strong>{html.escape(step.label)}</strong>"
            f"<em>{current_note}</em>"
            "</li>"
        )
    return (
        '<footer class="pipeline" aria-label="制作流水线">'
        "<h2>制作流水线</h2>"
        f'<ol class="pipeline-track">{"".join(items)}</ol>'
        "</footer>"
    )


def _chapter_link(chapter: Chapter, active_chapter_id: int | None, locale: str) -> str:
    active_class = " active" if chapter.id == active_chapter_id else ""
    status_class = html.escape(chapter.status.value)
    status = html.escape(_chapter_status_label(chapter.status, locale))
    href = f"/chapter/{chapter.id or 0}"
    return (
        f'<a class="chapter-row {status_class}{active_class}" href="{href}">'
        f"<span>{chapter.number:02d}</span>"
        f"<strong>{html.escape(chapter.title)}</strong>"
        f"<em>{status}</em></a>"
    )


def _book_status_label(status: BookStatus | str) -> str:
    value = status.value if isinstance(status, BookStatus) else str(status)
    return {
        BookStatus.DRAFT.value: "草稿",
        BookStatus.CANON_LOCKED.value: "可信设定已锁定",
        BookStatus.PRODUCING.value: "连载生产中",
        BookStatus.PAUSED.value: "已暂停",
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


def app_css() -> str:
    return """
    :root{color-scheme:light;--bg:#f7f8f4;--panel:#fffefa;--panel-soft:#fbfcf8;--ink:#1d2822;--muted:#68756d;--line:#dbe2d8;--accent:#426f4e;--accent-2:#edf4ea;--warn:#c47a16;--warn-soft:#fff7ea;--danger:#b94435;--shadow:0 18px 50px rgba(29,40,34,.06)}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}a{color:inherit;text-decoration:none}
    .app-shell{display:grid;grid-template-columns:112px 1fr;height:100vh;overflow:hidden}.rail{border-right:1px solid var(--line);background:#fbfcf8;display:flex;flex-direction:column;align-items:stretch;padding:18px 8px;gap:14px;min-height:0}.brand{display:grid;justify-items:center;gap:6px;padding:4px 0 16px}.brand-mark{width:30px;height:30px;border:2px solid var(--accent);border-radius:9px;display:grid;place-items:center;color:var(--accent);font-weight:800}.brand strong{font-size:20px}.nav-stack,.nav-bottom{display:grid;gap:6px}.nav-bottom{margin-top:auto}.nav-item{position:relative;border-radius:8px;padding:9px 6px;display:grid;justify-items:center;gap:4px;color:var(--muted);font-size:13px}.nav-item.active,.nav-item:hover{background:var(--accent-2);color:var(--accent)}.nav-item.active:before{content:"";position:absolute;left:-8px;top:10px;bottom:10px;width:3px;background:var(--accent);border-radius:999px}.nav-icon{font-size:22px;line-height:1}
    .workspace{display:flex;flex-direction:column;min-width:0;height:100vh;overflow:hidden}.topbar{height:62px;flex:0 0 62px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 28px;background:#fffefa}.top-actions{display:flex;align-items:center;gap:18px;color:var(--muted);font-size:13px}.eyebrow{font-size:20px;font-weight:800;color:var(--ink)}.notice{margin:16px 24px 0;color:var(--warn)}
    .content-grid{display:grid;grid-template-columns:280px minmax(0,1fr) 360px;gap:12px;padding:12px;flex:1 1 auto;min-height:0;overflow:auto}.content-grid.narrow-layout{grid-template-columns:minmax(0,860px);justify-content:center}.content-grid.model-setup-layout{grid-template-columns:220px minmax(0,1fr) 420px}.content-grid.canon-gate-layout{grid-template-columns:220px minmax(0,1fr) 370px}.content-grid.production-layout{grid-template-columns:280px minmax(0,1fr) 340px}.main-panel,.right-panel,.side-panel,.reader-panel,.empty-hero,.project-context{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:18px;box-shadow:var(--shadow)}.main-panel.single{grid-column:1 / -1}.empty-hero{grid-column:1 / 3;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;min-height:560px}.hidden-model-form{display:none}.book-mark{font-size:42px;color:var(--accent);margin-bottom:20px}
    .project-context{display:flex;flex-direction:column;gap:14px}.project-identity{display:grid;grid-template-columns:88px 1fr;gap:14px;align-items:start}.project-cover{width:88px;aspect-ratio:1;border-radius:8px;display:grid;place-items:center;color:#fff;font-size:34px;font-weight:800;background:linear-gradient(145deg,#344b3c,#849a7f)}.project-context h2{font-size:17px;line-height:1.35}.project-overview,.new-chapter{width:100%}
    h1{margin:0 0 8px;font-size:26px;line-height:1.2}h2{margin:0 0 12px;font-size:17px}h3{margin:18px 0 10px;font-size:14px;color:var(--muted)}p{margin:0 0 12px;color:var(--muted);line-height:1.6}.muted{color:var(--muted)}.panel-head,.chapter-toolbar{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:16px}
    .button,button{display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:0;border-radius:7px;background:var(--accent);color:#fff;cursor:pointer;font:inherit;font-weight:650;padding:9px 14px}.button.secondary,button.secondary{background:#fff;color:var(--ink);border:1px solid var(--line)}button:disabled,input:disabled{opacity:.55;cursor:not-allowed}.actions{display:flex;gap:10px;flex-wrap:wrap}.actions.center{justify-content:center}.compact-form,.form-grid{display:grid;gap:12px}.form-grid{grid-template-columns:1fr 1fr}.form-grid label:first-child,.form-grid label:nth-child(5),.form-grid .actions{grid-column:1 / -1}.split{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    label{display:grid;gap:6px;color:var(--muted);font-size:13px}input,textarea,select{width:100%;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);font:inherit;min-height:42px;padding:9px 11px}textarea{min-height:90px;resize:vertical}.inline-check{display:flex;align-items:center;gap:8px;color:var(--ink)}.inline-check input{width:auto;min-height:auto}
    .status-pill{display:inline-flex;align-items:center;border-radius:999px;padding:5px 10px;font-size:13px;background:#f4efe4;color:var(--warn)}.status-pill.trusted{background:var(--accent-2);color:var(--accent)}.pending{color:var(--warn)}.danger{color:var(--danger)}.local-note,.setup-card,.empty-box{border:1px solid var(--line);border-radius:8px;padding:14px;background:#fbfcf8}.local-note{display:grid;gap:4px;margin-top:24px;max-width:360px}.setup-card{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}
    .setup-project{padding:18px}.forest-cover{background:radial-gradient(circle at 30% 20%,#a7b59f,transparent 20%),linear-gradient(145deg,#2f4538,#6f846e 58%,#b4bda9)}.model-config-panel{padding:24px}.model-config-panel h2{font-size:18px;margin-top:26px}.info-dot{display:inline-grid;place-items:center;width:18px;height:18px;border:1px solid var(--line);border-radius:50%;font-size:12px;color:var(--muted)}.model-config-form{border:1px solid var(--line);border-radius:8px;padding:18px 20px;display:grid;gap:14px;background:#fff}.model-field{display:grid;grid-template-columns:136px minmax(0,1fr);align-items:start;gap:12px}.model-field label{font-size:15px;color:var(--ink);font-weight:650;padding-top:10px}.model-field p{grid-column:2;margin:0;color:var(--muted);font-size:12px}.input-shell,.select-shell{min-height:42px;border:1px solid var(--line);border-radius:7px;background:#fff;display:flex;align-items:center;gap:10px;padding:0 11px}.input-shell input{border:0;min-height:38px;padding:0;background:transparent}.field-status,.check-dot{color:var(--accent);font-weight:800}.select-shell{justify-content:space-between}.model-divider{height:1px;background:var(--line);margin:2px 0}.model-check{grid-template-columns:auto 1fr;margin-left:148px}.model-actions{border-top:1px solid var(--line);padding-top:16px;display:flex;gap:10px;justify-content:space-between}.setup-aside{display:grid;gap:14px;align-content:start}.setup-aside section{border:1px solid var(--line);border-radius:8px;padding:16px;background:#fff}.setup-checklist{list-style:none;margin:18px 0 0;padding:0;display:grid;gap:12px}.setup-checklist li{display:grid;grid-template-columns:24px 1fr;gap:10px;margin:0}.setup-checklist span{display:grid;place-items:center;width:22px;height:22px;border-radius:50%;border:1px solid var(--warn);color:var(--warn)}.setup-checklist .done span{border-color:var(--accent);background:var(--accent);color:#fff}.setup-checklist strong{font-size:14px}.setup-checklist p{font-size:12px;margin:2px 0 0}.local-database-card ul{list-style:none;padding:0;display:grid;gap:8px;color:var(--muted);font-size:13px}.db-path{font-size:12px;word-break:break-all;margin-top:10px}
    .step-list{margin:24px 0;padding-left:20px;color:var(--muted)}.step-list li{margin:14px 0}.step-list .active{color:var(--accent);font-weight:700}.stack-list{display:grid;gap:8px}.stack-list p,.project-row{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.project-list{display:grid;gap:10px}.project-row{display:flex;justify-content:space-between;align-items:center}
    .card-grid,.state-sections,.blueprint-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.state-link{margin-bottom:12px}.data-card,.table-card,.proposal-card,.quality-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:14px}.data-card h3{margin-top:0;color:var(--ink);font-size:15px}ul{margin:0;padding-left:20px}li{margin:5px 0;line-height:1.5}dl{display:grid;grid-template-columns:96px 1fr;gap:8px 12px}dt{color:var(--muted)}dd{margin:0}
    .canon-warning{border:1px solid #eacb90;border-radius:8px;background:var(--warn-soft);color:#6d4c16;padding:12px 14px;margin-bottom:14px}.canon-state-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.rhythm-board{margin-top:12px}.audit-risk-panel{display:grid;gap:12px;align-content:start}.audit-risk-panel section{border:1px solid var(--line);border-radius:8px;background:#fff;padding:14px}.risk-summary{display:flex;gap:16px;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:10px}.risk{font-weight:800}.risk.high,.risk-badge.high{color:#b94435}.risk.medium,.risk-badge.medium{color:#c47a16}.risk.low,.risk-badge.low{color:#426f4e}.risk-list{display:grid;gap:8px}.risk-list article{display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center;border-bottom:1px solid var(--line);padding:8px 0}.risk-badge{display:grid;place-items:center;width:24px;height:24px;border-radius:8px;background:#f8eee9;font-weight:800}.force-gate strong{color:var(--warn)}.gate-actions{display:grid;gap:8px}
    .blueprint-layout{grid-template-columns:minmax(0,1fr) 360px}.blueprint-main{min-width:0}.blueprint-actions{min-width:0}.proposal-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:12px}.proposal-card{display:grid;gap:10px}.proposal-card header{display:flex;justify-content:space-between;gap:8px}.proposal-card dl{grid-template-columns:78px 1fr}.proposal-card ol{margin:0;padding-left:20px;color:var(--muted)}
    .metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}.metric-grid div{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.metric-grid strong{font-size:26px;display:block}.metric-grid span{color:var(--muted);font-size:13px}.chapter-list{display:grid;gap:6px}.chapter-row{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:8px;align-items:center;border-radius:8px;padding:10px;color:var(--muted)}.chapter-row:hover,.chapter-row.active,.chapter-row.running,.chapter-row.awaiting_review,.chapter-row.accepted{background:var(--accent-2);color:var(--accent)}.chapter-row em{font-style:normal;font-size:12px}.chapter-row strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .production-main{grid-column:auto;padding:18px}.toolbar-metrics{display:flex;align-items:center;gap:16px;color:var(--muted);font-size:13px}.production-stage-grid{display:grid;grid-template-columns:repeat(7,minmax(112px,1fr));gap:10px;margin:8px 0 14px}.stage-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px;min-height:130px}.stage-card span{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#f0f3ed;color:var(--muted);font-weight:800}.stage-card h3{margin:8px 0 10px;color:var(--ink)}.stage-card strong{font-size:13px;color:var(--muted)}.stage-card p{font-size:12px;margin:8px 0 0}.stage-card.done{border-color:#bfd2bf}.stage-card.done span{background:var(--accent-2);color:var(--accent)}.stage-card.current{border-color:#e0a44a;background:#fffaf0}.stage-card.current span{background:#e19a18;color:#fff}.stage-card.current strong{color:#c47a16}.production-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}.production-grid .data-card{min-height:160px}.draft-snippet{border:1px solid var(--line);border-radius:8px;background:#fbfcf8;padding:10px}.trace-preview,.recovery-list{list-style:none;padding:0}.status-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}.status-dot.done{background:var(--accent)}.status-dot.warn{background:var(--warn)}.production-aside{display:grid;gap:10px;align-content:start}.production-aside section{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.gate-list{display:grid;gap:4px}.gate-list article{display:grid;grid-template-columns:34px 1fr;gap:8px;align-items:center;border-bottom:1px solid var(--line);padding:6px 0}.gate-icon{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#f4efe4;color:var(--warn);font-weight:800}.current-run dl{grid-template-columns:1fr auto}
    table{width:100%;border-collapse:collapse;font-size:14px}td{border-bottom:1px solid var(--line);padding:10px 8px;vertical-align:top}.reader-panel{grid-column:2 / 3}.chapter-text{min-height:560px;border-top:1px solid var(--line);padding:28px 64px;font-size:19px;line-height:2;color:#222;white-space:normal}.manual-edit{border-top:1px solid var(--line);padding-top:14px;display:grid;gap:12px}.manual-edit textarea[name=manual_text]{min-height:260px;font-size:17px;line-height:1.8}.note-box{border-top:1px solid var(--line);padding-top:14px}.review-tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;border-bottom:1px solid var(--line);margin:-4px 0 14px}.review-tabs span{padding:10px 4px;text-align:center;color:var(--muted);font-size:13px}.review-tabs .active{color:var(--accent);box-shadow:inset 0 -2px 0 var(--accent);font-weight:800}.review-list{display:grid;gap:8px;padding:0;list-style:none}.review-list li{border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px;display:grid;gap:4px}.review-list em{font-style:normal;color:var(--muted);font-size:12px}.impact-scope{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}.impact-scope>div{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.impact-scope section{border:1px solid var(--line);border-radius:8px;padding:10px;background:#fff}.review-action-stack{display:grid;grid-template-columns:1fr 1fr;gap:8px;border-top:1px solid var(--line);padding-top:10px;margin-top:10px}.review-action-stack .action-form{border-top:0;margin-top:0;padding-top:0}.review-action-stack .action-form:last-child{grid-column:1 / -1}.accepted-result{display:grid;gap:10px;margin-bottom:12px}.accepted-result .stack-list p{display:flex;justify-content:space-between}
    .choice-list{display:grid;gap:8px}.choice{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:11px;color:var(--ink)}.choice input{width:auto;min-height:auto}.action-form{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}
    .pipeline{min-height:108px;flex:0 0 108px;border-top:1px solid var(--line);background:#fffefa;display:grid;grid-template-columns:160px 1fr;align-items:center;gap:20px;padding:16px 24px;overflow:auto}.pipeline h2{margin:0;font-size:18px}.pipeline-track{display:flex;align-items:center;gap:10px;margin:0;padding:0;list-style:none;min-width:max-content}.pipeline-step{width:112px;display:grid;justify-items:center;gap:4px;text-align:center;color:var(--muted);margin:0}.pipeline-step strong{font-size:13px}.pipeline-step em{font-style:normal;font-size:12px}.pipeline-icon{width:30px;height:30px;border:1px solid var(--line);border-radius:999px;display:grid;place-items:center;background:#fff}.pipeline-step.done{color:var(--accent)}.pipeline-step.done .pipeline-icon{background:var(--accent-2);border-color:var(--accent)}.pipeline-step.current{color:var(--warn)}.pipeline-step.current .pipeline-icon{background:var(--warn-soft);border-color:var(--warn)}.pipeline-connector{width:48px;border-top:1px solid var(--line)}
    .quality-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.quality-card form,.update-main form{display:grid;gap:10px;border-top:1px solid var(--line);padding-top:12px;margin-top:12px}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metrics div,.strategy{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.metrics strong{display:block;font-size:24px}.metrics span{color:var(--muted);font-size:13px}.update-main{align-self:start}.update-main dl{margin:0 0 14px}
    @media(max-width:1100px){.app-shell{grid-template-columns:82px 1fr}.rail strong{font-size:13px}.content-grid,.blueprint-layout,.content-grid.model-setup-layout,.content-grid.canon-gate-layout,.content-grid.production-layout{grid-template-columns:1fr}.empty-hero,.reader-panel{grid-column:auto}.form-grid,.card-grid,.state-sections,.blueprint-detail-grid,.proposal-grid,.split,.quality-grid,.canon-state-grid,.production-grid,.production-stage-grid,.impact-scope>div{grid-template-columns:1fr}.model-field{grid-template-columns:1fr}.model-field p{grid-column:auto}.model-check{margin-left:0}.top-actions{display:none}.pipeline{grid-template-columns:1fr}.project-identity{grid-template-columns:64px 1fr}.project-cover{width:64px}}
    """
