from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from mynovel.domain.models import Book, BookStatus, Chapter, ChapterStatus
from mynovel.i18n import DEFAULT_LOCALE, t
from mynovel.path_display import display_path
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
    status_strip: str | None = None,
) -> str:
    nav_links = project_nav_links(nav_book_id)
    project_mode = nav_book_id is not None
    notification = (
        '<span class="notification-badge" aria-hidden="true">3</span>' if project_mode else ""
    )
    author_menu = (
        '<span class="author-menu"><span class="author-avatar" aria-hidden="true"></span><span>作者⌄</span></span>'
        if project_mode
        else ""
    )
    db_hint = (
        f"<span class='sr-only'>{t('app.local_database', locale)}：{html.escape(display_path(db_path))}</span>"
        if db_path
        else ""
    )
    shell_status_strip = status_strip or ""
    return f"""<!doctype html>
<html lang="{locale}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{app_css()}</style>
</head>
<body>
  <!-- class="app-shell" -->
  <div class="app-shell app-shell-compact">
    <header class="topbar">
      <a class="brand" href="/" aria-label="MyNovel">
        {_brand_mark()}<strong>MyNovel</strong>
      </a>
      <div class="top-actions">
        <a href="/">{_icon("book-open")}<span>查看日志</span></a>
        <span class="top-separator" aria-hidden="true"></span>
        <a class="sr-only" href="/provider-config">模型接口设置</a>
        <a class="notification-link" href="/review" aria-label="通知">{_icon("bell")}{notification}</a>
        <a href="/updates">{_icon("settings")}<span>设置</span></a>
        {author_menu}
        {db_hint}
      </div>
    </header>
    <nav class="rail" aria-label="主导航">
      <div class="nav-stack">
        {render_nav_item("/", t("nav.workspace", locale), "home", active == "workspace")}
        {render_nav_item("/books/new", t("nav.create", locale), "book-open", active == "create")}
        {render_nav_item(nav_links.docs, t("nav.docs", locale), "file-text", active == "docs")}
        {render_nav_item(nav_links.characters, "角色", "user", active == "characters")}
        {render_nav_item(nav_links.world, "世界观", "globe", active == "world")}
        {render_nav_item(nav_links.analysis, "分析", "bar-chart", active == "analysis")}
        {render_nav_item("/review", t("nav.review", locale), "shield-check", active == "review")}
      </div>
      <div class="nav-bottom">
        {render_nav_item("/updates", t("nav.settings", locale), "settings", active == "settings")}
      </div>
    </nav>
    <main class="workspace">
      <span class="page-eyebrow sr-only">{html.escape(eyebrow or t("app.product_mode", locale))}</span>
      {shell_status_strip}
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
    rendered_icon = _icon(icon) if icon in ICON_PATHS else html.escape(icon)
    return (
        f'<a class="nav-item{active_class}" href="{html.escape(href, quote=True)}">'
        f'<span class="nav-icon" aria-hidden="true">{rendered_icon}</span>'
        f"<span>{html.escape(label)}</span></a>"
    )


ICON_PATHS = {
    "bar-chart": '<path d="M4 19V9"/><path d="M10 19V5"/><path d="M16 19v-7"/><path d="M22 19V3"/>',
    "bell": '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/>',
    "book-open": '<path d="M12 7v14"/><path d="M4 5.5c3.5-.7 6.2.1 8 2.1 1.8-2 4.5-2.8 8-2.1V19c-3.5-.7-6.2.1-8 2.1-1.8-2-4.5-2.8-8-2.1Z"/>',
    "file-text": '<path d="M7 3h7l4 4v14H7Z"/><path d="M14 3v5h5"/><path d="M9.5 12h5"/><path d="M9.5 16h7"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.4 2.5 3.6 5.5 3.6 9S14.4 18.5 12 21c-2.4-2.5-3.6-5.5-3.6-9S9.6 5.5 12 3Z"/>',
    "home": '<path d="M4 11.5 12 4l8 7.5"/><path d="M6.5 10.5V20h11v-9.5"/><path d="M10 20v-5h4v5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12.2 2h-.4a2 2 0 0 0-2 2v.2a2 2 0 0 1-1 1.7l-.4.2a2 2 0 0 1-2 0l-.2-.1a2 2 0 0 0-2.7.7l-.2.4A2 2 0 0 0 4 9.8l.2.1a2 2 0 0 1 1 1.7v.6a2 2 0 0 1-1 1.7l-.2.1a2 2 0 0 0-.7 2.7l.2.4a2 2 0 0 0 2.7.7l.2-.1a2 2 0 0 1 2 0l.4.2a2 2 0 0 1 1 1.7v.2a2 2 0 0 0 2 2h.4a2 2 0 0 0 2-2v-.2a2 2 0 0 1 1-1.7l.4-.2a2 2 0 0 1 2 0l.2.1a2 2 0 0 0 2.7-.7l.2-.4A2 2 0 0 0 20 14l-.2-.1a2 2 0 0 1-1-1.7v-.6a2 2 0 0 1 1-1.7l.2-.1a2 2 0 0 0 .7-2.7l-.2-.4a2 2 0 0 0-2.7-.7l-.2.1a2 2 0 0 1-2 0l-.4-.2a2 2 0 0 1-1-1.7V4a2 2 0 0 0-2-2Z"/>',
    "shield-check": '<path d="M12 3 20 6v6c0 5-3.3 8-8 9-4.7-1-8-4-8-9V6Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/>',
    "user": '<circle cx="12" cy="8" r="3"/><path d="M6 20c.7-3.2 2.7-5 6-5s5.3 1.8 6 5"/>',
}


def _brand_mark() -> str:
    return (
        '<span class="brand-mark" aria-hidden="true">'
        '<svg viewBox="0 0 40 40" focusable="false">'
        '<path d="M20 3 34 10v16L20 37 6 26V10Z" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linejoin="round"/>'
        '<path d="m13 16 5.2 10.5L28 11" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg></span>"
    )


def _icon(name: str) -> str:
    path = ICON_PATHS[name]
    return (
        '<svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        f"{path}"
        "</svg>"
    )


def render_project_sidebar(
    book: Book,
    chapters: list[Chapter],
    *,
    active_chapter_id: int | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    title = html.escape(book.title)
    rows = "".join(
        _chapter_link(chapter, active_chapter_id, locale)
        for chapter in sorted(chapters, key=lambda item: item.number)
    )
    if not rows:
        rows = '<p class="muted">暂无章节。</p>'
    return f"""
      <aside class="project-context">
        <div class="project-identity">
          <div class="project-cover forest-cover" aria-hidden="true"></div>
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


def render_pipeline(
    steps: list[PipelineStep],
    *,
    title: str = "制作流水线",
    element_id: str | None = None,
) -> str:
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
    id_attr = f' id="{html.escape(element_id, quote=True)}"' if element_id else ""
    safe_title = html.escape(title)
    return (
        f'<footer class="pipeline"{id_attr} aria-label="{safe_title}">'
        f"<h2>{safe_title}<span class='info-dot' aria-hidden='true'>?</span></h2>"
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
    :root{color-scheme:light;--bg-canvas:#f3f0e6;--bg:#f7f4eb;--panel:#fcfaf3;--panel-elevated:#fffdf8;--panel-soft:#f6f1e3;--ink:#1d2822;--muted:#657168;--line:#d8ddd3;--accent:#426f4e;--accent-strong:#264f35;--accent-2:#e6f0e6;--warn:#c47a16;--warn-soft:#fff7ea;--danger:#b94435;--shadow:0 18px 50px rgba(29,40,34,.06)}
    *{box-sizing:border-box}body{margin:0;background:var(--bg-canvas);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}a{color:inherit;text-decoration:none}
    .app-shell{display:grid;grid-template-columns:144px 1fr;grid-template-rows:84px minmax(0,1fr);height:100vh;overflow:hidden}.app-shell-compact{background:linear-gradient(180deg,#f8f5ed 0%,var(--bg-canvas) 100%)}.topbar{grid-column:1 / -1;grid-row:1;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 32px;background:rgba(252,250,243,.94);backdrop-filter:saturate(140%) blur(12px)}.brand{display:flex;align-items:center;gap:14px}.brand-mark{width:40px;height:40px;display:grid;place-items:center;color:var(--accent-strong)}.brand-mark svg{width:40px;height:40px}.brand strong{font-size:26px;letter-spacing:0}.top-actions{display:flex;align-items:center;gap:22px;color:#2a332e;font-size:16px}.top-actions a{display:inline-flex;align-items:center;gap:8px}.top-separator{width:1px;height:30px;background:var(--line)}.icon-svg{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}.rail{grid-column:1;grid-row:2;border-right:1px solid var(--line);background:#f8f5ed;display:flex;flex-direction:column;align-items:stretch;padding:18px 10px;gap:14px;min-height:0}.nav-stack,.nav-bottom{display:grid;gap:8px}.nav-bottom{margin-top:auto}.nav-item{position:relative;border-radius:8px;padding:13px 6px;display:grid;justify-items:center;gap:8px;color:#3f4844;font-size:16px}.nav-item.active,.nav-item:hover{background:var(--accent-2);color:var(--accent-strong)}.nav-item.active:before{content:"";position:absolute;left:-10px;top:0;bottom:0;width:4px;background:var(--accent-strong);border-radius:999px}.nav-icon{width:32px;height:32px;display:grid;place-items:center}.nav-icon .icon-svg{width:30px;height:30px;stroke-width:1.8}
    .workspace{grid-column:2;grid-row:2;display:flex;flex-direction:column;min-width:0;min-height:0;overflow:hidden;background:var(--bg-canvas)}.global-status-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;padding:14px 22px 0}.status-stage{display:grid;gap:6px;padding:14px 16px;border:1px solid var(--line);border-radius:10px;background:var(--panel-elevated);box-shadow:var(--shadow);min-width:0}.status-stage.current{border-color:rgba(38,79,53,.24);background:linear-gradient(180deg,#f8fbf7 0%,var(--panel-elevated) 100%)}.status-stage.working{border-color:rgba(66,111,78,.18)}.status-stage.decision{border-color:rgba(196,122,22,.24);background:linear-gradient(180deg,#fffaf1 0%,var(--panel-elevated) 100%)}.status-stage-label{margin:0;color:var(--accent-strong);font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}.status-stage strong{font-size:18px;line-height:1.3}.status-stage span{color:var(--muted);font-size:13px;line-height:1.5}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.notice{margin:16px 24px 0;color:var(--warn)}
    .content-grid{display:grid;grid-template-columns:280px minmax(0,1fr) 360px;gap:12px;padding:12px;flex:1 1 auto;min-height:0;overflow:auto}.content-grid.narrow-layout{grid-template-columns:minmax(0,860px);justify-content:center}.content-grid.model-setup-layout{grid-template-columns:220px minmax(0,1fr) 420px}.content-grid.canon-gate-layout{grid-template-columns:220px minmax(0,1fr) 370px}.content-grid.production-layout{grid-template-columns:280px minmax(0,1fr) 340px}.main-panel,.right-panel,.side-panel,.reader-panel,.empty-hero,.project-context,.launch-card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:18px;box-shadow:var(--shadow)}.main-panel.single{grid-column:1 / -1}.hidden-model-form{display:none}.book-mark{font-size:42px;color:var(--accent);margin-bottom:20px}
    .first-launch-layout{grid-template-columns:minmax(560px,calc(100% - 708px)) 572px;gap:36px;padding:20px 48px 0;align-items:start}.first-launch-hero{min-height:650px;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;padding-top:102px}.empty-book-illustration{width:106px;color:var(--accent);filter:drop-shadow(0 16px 22px rgba(66,111,78,.14));margin-bottom:22px}.first-launch-hero h1{font-size:40px;margin:0 0 18px;letter-spacing:0}.first-launch-hero p{font-size:16px;margin:0 0 4px}.launch-actions{display:grid;gap:16px;width:360px;margin-top:48px}.first-launch-aside{display:grid;gap:16px;align-content:start}.launch-card{box-shadow:none;background:#fffefa;padding:18px}.launch-card header{display:flex;align-items:center;justify-content:space-between;gap:14px;border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:18px}.launch-card h2{font-size:23px;margin:0}.compact-button{min-height:42px;padding:8px 14px;color:var(--accent);font-weight:700}.recent-empty{min-height:148px;display:grid;place-items:center;text-align:center;color:var(--muted)}.empty-file-icon{display:grid;place-items:center;width:54px;height:64px;border:3px solid #c9ceca;border-radius:14px;color:#a8afaa;font-size:28px}.model-status-card{padding-top:22px;padding-bottom:22px}.model-ready-row{border:1px solid #ead8bd;background:#fffaf1;border-radius:8px;padding:24px 18px;display:grid;grid-template-columns:34px 1fr auto;align-items:center;gap:14px}.warn-icon{display:grid;place-items:center;color:var(--warn);font-size:32px}.model-ready-row strong{font-size:22px}.model-ready-row p{margin:4px 0 0;font-size:14px}.quickstart-list{display:grid;gap:0;border:1px solid var(--line);border-radius:8px;overflow:hidden}.quickstart-row{display:grid;grid-template-columns:46px 1fr auto;align-items:center;gap:12px;min-height:76px;padding:14px 16px;background:#fff;border-bottom:1px solid var(--line)}.quickstart-row:last-child{border-bottom:0}.quickstart-row:hover{background:var(--panel-soft)}.quickstart-icon{display:grid;place-items:center;width:38px;height:38px;border:1px solid var(--line);border-radius:8px;color:var(--accent);font-size:23px}.quickstart-row strong{display:block;font-size:18px;margin-bottom:4px}.quickstart-row em{display:block;font-style:normal;color:var(--muted);font-size:14px}.quickstart-row b{font-size:30px;color:var(--muted);font-weight:400}
    .project-context{display:flex;flex-direction:column;gap:14px}.project-identity{display:grid;grid-template-columns:88px 1fr;gap:14px;align-items:start}.project-cover{width:88px;aspect-ratio:1;border-radius:8px;display:grid;place-items:center;color:#fff;font-size:34px;font-weight:800;background:linear-gradient(145deg,#344b3c,#849a7f)}.project-context h2{font-size:17px;line-height:1.35}.project-overview,.new-chapter{width:100%}
    h1{margin:0 0 8px;font-size:26px;line-height:1.2}h2{margin:0 0 12px;font-size:17px}h3{margin:18px 0 10px;font-size:14px;color:var(--muted)}p{margin:0 0 12px;color:var(--muted);line-height:1.6}.muted{color:var(--muted)}.panel-head,.chapter-toolbar{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:16px}
    .button,button{display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:0;border-radius:7px;background:var(--accent);color:#fff;cursor:pointer;font:inherit;font-weight:650;padding:9px 14px}.button.secondary,button.secondary{background:#fff;color:var(--ink);border:1px solid var(--line)}.button.launch-primary,.button.launch-secondary{min-height:60px;font-size:22px;gap:14px}.button.launch-secondary{background:#fff;border-color:#d5ddd3;color:var(--ink)}button:disabled,input:disabled{opacity:.55;cursor:not-allowed}.actions{display:flex;gap:10px;flex-wrap:wrap}.actions.center{justify-content:center}.compact-form,.form-grid{display:grid;gap:12px}.form-grid{grid-template-columns:1fr 1fr}.form-grid label:first-child,.form-grid label:nth-child(5),.form-grid .actions{grid-column:1 / -1}.split{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    label{display:grid;gap:6px;color:var(--muted);font-size:13px}input,textarea,select{width:100%;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);font:inherit;min-height:42px;padding:9px 11px}textarea{min-height:90px;resize:vertical}.inline-check{display:flex;align-items:center;gap:8px;color:var(--ink)}.inline-check input{width:auto;min-height:auto}
    .status-pill{display:inline-flex;align-items:center;border-radius:999px;padding:5px 10px;font-size:13px;background:#f4efe4;color:var(--warn)}.status-pill.trusted{background:var(--accent-2);color:var(--accent)}.pending{color:var(--warn)}.danger{color:var(--danger)}.local-note,.setup-card,.empty-box{border:1px solid var(--line);border-radius:8px;padding:14px;background:#fbfcf8}.local-note{display:grid;gap:4px;margin-top:24px;max-width:360px}.setup-card{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}
    .setup-project{padding:18px}.forest-cover{background:radial-gradient(circle at 30% 20%,#a7b59f,transparent 20%),linear-gradient(145deg,#2f4538,#6f846e 58%,#b4bda9)}.model-config-panel{padding:24px}.model-config-panel h2{font-size:18px;margin-top:26px}.info-dot{display:inline-grid;place-items:center;width:18px;height:18px;border:1px solid var(--line);border-radius:50%;font-size:12px;color:var(--muted)}.model-config-form{border:1px solid var(--line);border-radius:8px;padding:18px 20px;display:grid;gap:14px;background:#fff}.model-credential-section{display:grid;gap:14px}.model-credential-section header{display:grid;gap:4px}.model-credential-section h3{margin:0;color:var(--ink);font-size:16px}.model-credential-section p{margin:0}.model-field{display:grid;grid-template-columns:136px minmax(0,1fr);align-items:start;gap:12px}.model-field label{font-size:15px;color:var(--ink);font-weight:650;padding-top:10px}.model-field p{grid-column:2;margin:0;color:var(--muted);font-size:12px}.input-shell,.select-shell{min-height:42px;border:1px solid var(--line);border-radius:7px;background:#fff;display:flex;align-items:center;gap:10px;padding:0 11px}.input-shell input{border:0;min-height:38px;padding:0;background:transparent}.field-status,.check-dot{color:var(--accent);font-weight:800}.select-shell{justify-content:space-between}.model-divider{height:1px;background:var(--line);margin:2px 0}.model-check{grid-template-columns:auto 1fr;margin-left:148px}.model-actions{border-top:1px solid var(--line);padding-top:16px;display:flex;gap:10px;justify-content:space-between}.setup-aside{display:grid;gap:14px;align-content:start}.setup-aside section{border:1px solid var(--line);border-radius:8px;padding:16px;background:#fff}.setup-checklist{list-style:none;margin:18px 0 0;padding:0;display:grid;gap:12px}.setup-checklist li{display:grid;grid-template-columns:24px 1fr;gap:10px;margin:0}.setup-checklist span{display:grid;place-items:center;width:22px;height:22px;border-radius:50%;border:1px solid var(--warn);color:var(--warn)}.setup-checklist .done span{border-color:var(--accent);background:var(--accent);color:#fff}.setup-checklist strong{font-size:14px}.setup-checklist p{font-size:12px;margin:2px 0 0}.local-database-card ul{list-style:none;padding:0;display:grid;gap:8px;color:var(--muted);font-size:13px}.db-path{font-size:12px;word-break:break-all;margin-top:10px}
    .step-list{margin:24px 0;padding-left:20px;color:var(--muted)}.step-list li{margin:14px 0}.step-list .active{color:var(--accent);font-weight:700}.stack-list{display:grid;gap:8px}.stack-list p,.project-row{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.project-list{display:grid;gap:10px}.project-row{display:flex;justify-content:space-between;align-items:center}
    .card-grid,.state-sections,.blueprint-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.state-link{margin-bottom:12px}.data-card,.table-card,.proposal-card,.quality-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:14px}.data-card h3{margin-top:0;color:var(--ink);font-size:15px}ul{margin:0;padding-left:20px}li{margin:5px 0;line-height:1.5}dl{display:grid;grid-template-columns:96px 1fr;gap:8px 12px}dt{color:var(--muted)}dd{margin:0}
    .canon-warning{border:1px solid #eacb90;border-radius:8px;background:var(--warn-soft);color:#6d4c16;padding:12px 14px;margin-bottom:14px}.canon-state-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.rhythm-board{margin-top:12px}.audit-risk-panel{display:grid;gap:12px;align-content:start}.audit-risk-panel section{border:1px solid var(--line);border-radius:8px;background:#fff;padding:14px}.risk-summary{display:flex;gap:16px;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:10px}.risk{font-weight:800}.risk.high,.risk-badge.high{color:#b94435}.risk.medium,.risk-badge.medium{color:#c47a16}.risk.low,.risk-badge.low{color:#426f4e}.risk-list{display:grid;gap:8px}.risk-list article{display:grid;grid-template-columns:28px 1fr auto;gap:10px;align-items:center;border-bottom:1px solid var(--line);padding:8px 0}.risk-badge{display:grid;place-items:center;width:24px;height:24px;border-radius:8px;background:#f8eee9;font-weight:800}.force-gate strong{color:var(--warn)}.gate-actions{display:grid;gap:8px}
    .blueprint-layout{grid-template-columns:280px minmax(0,1fr)}.blueprint-main{min-width:0}.blueprint-actions{grid-column:2;min-width:0}.proposal-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:12px}.proposal-card{display:grid;gap:10px}.proposal-card header{display:flex;justify-content:space-between;gap:8px}
    .metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px}.metric-grid div{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.metric-grid strong{font-size:26px;display:block}.metric-grid span{color:var(--muted);font-size:13px}.chapter-list{display:grid;gap:6px}.chapter-row{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:8px;align-items:center;border-radius:8px;padding:10px;color:var(--muted)}.chapter-row:hover,.chapter-row.active,.chapter-row.running,.chapter-row.awaiting_review,.chapter-row.accepted{background:var(--accent-2);color:var(--accent)}.chapter-row em{font-style:normal;font-size:12px}.chapter-row strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .production-main{grid-column:auto;padding:18px}.toolbar-metrics{display:flex;align-items:center;gap:16px;color:var(--muted);font-size:13px}.run-status-strip{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:14px;border:1px solid #d9e5d6;border-radius:8px;background:#f8fbf6;padding:12px 14px;margin-bottom:14px}.run-status-strip strong{font-size:16px}.run-status-strip span{color:var(--muted);font-size:13px}.production-stage-grid{display:grid;grid-template-columns:repeat(7,minmax(112px,1fr));gap:10px;margin:8px 0 14px}.stage-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px;min-height:130px}.stage-card span{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#f0f3ed;color:var(--muted);font-weight:800}.stage-card h3{margin:8px 0 10px;color:var(--ink)}.stage-card strong{font-size:13px;color:var(--muted)}.stage-card p{font-size:12px;margin:8px 0 0}.stage-card.done{border-color:#bfd2bf}.stage-card.done span{background:var(--accent-2);color:var(--accent)}.stage-card.current{border-color:#e0a44a;background:#fffaf0}.stage-card.current span{background:#e19a18;color:#fff}.stage-card.current strong{color:#c47a16}.production-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}.production-grid .data-card{min-height:160px}.draft-snippet{border:1px solid var(--line);border-radius:8px;background:#fbfcf8;padding:10px}.status-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}.status-dot.done{background:var(--accent)}.status-dot.warn{background:var(--warn)}.production-aside{display:grid;gap:10px;align-content:start}.production-aside section{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.gate-list{display:grid;gap:4px}.gate-list article{display:grid;grid-template-columns:34px 1fr;gap:8px;align-items:center;border-bottom:1px solid var(--line);padding:6px 0}.gate-icon{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#f4efe4;color:var(--warn);font-weight:800}.current-run dl{grid-template-columns:86px minmax(0,1fr)}.current-run dd{min-width:0;overflow-wrap:anywhere}
    table{width:100%;border-collapse:collapse;font-size:14px}td{border-bottom:1px solid var(--line);padding:10px 8px;vertical-align:top}.reader-panel{grid-column:2 / 3}.chapter-text{min-height:560px;border-top:1px solid var(--line);padding:28px 64px;font-size:19px;line-height:2;color:#222;white-space:normal}.manual-edit{border-top:1px solid var(--line);padding-top:14px;display:grid;gap:12px}.manual-edit textarea[name=manual_text]{min-height:260px;font-size:17px;line-height:1.8}.note-box{border-top:1px solid var(--line);padding-top:14px}.review-inspector-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:12px}.review-inspector-head h2{font-size:18px;margin:2px 0 0}.review-inspector-head .risk-badge{width:auto;height:auto;padding:6px 10px;border-radius:999px;white-space:nowrap}.review-tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;border-bottom:1px solid var(--line);margin:-4px 0 14px}.review-tab-button{appearance:none;border:0;background:transparent;border-radius:0;padding:10px 4px;text-align:center;color:var(--muted);font-size:13px;cursor:pointer;display:grid;gap:2px;min-width:0}.review-tab-button span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.review-tab-button em{font-style:normal;font-size:11px;color:var(--muted)}.review-tab-button.active{color:var(--accent);box-shadow:inset 0 -2px 0 var(--accent);font-weight:800}.review-tab-button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.review-tab-panel[hidden]{display:none}.review-panel-copy{color:var(--muted);font-size:13px;margin-top:0}.review-list{display:grid;gap:8px;padding:0;list-style:none}.review-list li{border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px;display:grid;gap:4px}.review-list em{font-style:normal;color:var(--muted);font-size:12px}.structured-review-list li{border-left:3px solid #dce6d9}.review-row-meta{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px}.review-row-meta b{display:inline-grid;place-items:center;min-width:22px;height:22px;border-radius:999px;background:#f0f3ed;color:var(--accent)}.review-row-meta .needs-confirm{color:#c47a16}.review-row-meta .fixed{color:#426f4e}.empty-review-row span{font-weight:800;color:var(--ink)}.raw-state-delta{margin-top:10px}.raw-state-delta summary{cursor:pointer;color:var(--accent);font-weight:800}.raw-state-delta pre{white-space:pre-wrap;max-height:240px;overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fbfcf8;padding:10px}.revision-metrics{display:grid;grid-template-columns:1fr auto;gap:8px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px}.revision-excerpt{border-left:3px solid var(--accent);margin:12px 0 0;padding:8px 0 8px 12px;color:var(--muted)}.repair-trace-panel{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}.repair-trace-panel h2{font-size:16px}.repair-trace-metrics{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.repair-trace-metrics span{border:1px solid var(--line);border-radius:999px;background:#fff;padding:5px 10px;color:var(--muted);font-size:12px}.repair-trace-panel details{margin-top:8px}.repair-trace-panel summary{cursor:pointer;color:var(--accent);font-weight:800}.repair-trace-panel pre{white-space:pre-wrap;max-height:260px;overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fbfcf8;padding:10px}.impact-scope{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}.inline-impact-scope{border-top:0;margin-top:0;padding-top:0}.impact-scope>div{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.impact-scope section{border:1px solid var(--line);border-radius:8px;padding:10px;background:#fff}.review-decision-summary{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}.review-action-stack{display:grid;grid-template-columns:1fr 1fr;gap:8px;border-top:1px solid var(--line);padding-top:10px;margin-top:10px}.review-action-stack .action-form{border-top:0;margin-top:0;padding-top:0}.review-action-stack .action-form:last-child{grid-column:1 / -1}.accepted-result{display:grid;gap:10px;margin-bottom:12px}.accepted-result .stack-list p{display:flex;justify-content:space-between}
    .choice-list{display:grid;gap:8px}.choice{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:11px;color:var(--ink)}.choice input{width:auto;min-height:auto}.action-form{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}
    .pipeline{flex:0 0 108px;min-height:108px;margin:0 22px 14px;border:1px solid var(--line);border-radius:8px;background:#fffefa;display:grid;grid-template-columns:minmax(0,1fr);align-items:start;gap:8px;padding:12px 20px 10px;overflow:auto}.pipeline h2{margin:0;font-size:17px;display:flex;align-items:center;gap:8px}.pipeline-track{grid-column:1 / -1;display:flex;align-items:flex-start;justify-content:space-around;gap:10px;margin:0;padding:0;list-style:none;min-width:0}.pipeline-step{width:98px;display:grid;justify-items:center;gap:2px;text-align:center;color:var(--muted);margin:0}.pipeline-step strong{font-size:14px;color:var(--ink)}.pipeline-step em{font-style:normal;font-size:12px;line-height:1.2}.pipeline-icon{width:34px;height:34px;border:1px solid var(--line);border-radius:999px;display:grid;place-items:center;background:#fff;font-size:17px}.pipeline-step.done{color:var(--accent)}.pipeline-step.done .pipeline-icon{background:var(--accent-2);border-color:var(--accent)}.pipeline-step.current{color:var(--warn)}.pipeline-step.current .pipeline-icon{background:var(--warn-soft);border-color:var(--warn)}.pipeline-step.locked .pipeline-icon{color:#38413d}.pipeline-step.locked em:before{content:"▣";font-size:11px;color:#9ca39e;margin-right:8px}.pipeline-connector{flex:0 1 88px;min-width:42px;border-top:2px dashed #c6cdc8;position:relative;margin-top:16px}.pipeline-connector:after{content:"";position:absolute;right:0;top:-5px;width:8px;height:8px;border-right:2px solid #c6cdc8;border-top:2px solid #c6cdc8;transform:rotate(45deg)}
    .quality-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.quality-card form,.update-main form{display:grid;gap:10px;border-top:1px solid var(--line);padding-top:12px;margin-top:12px}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metrics div,.strategy{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.metrics strong{display:block;font-size:24px}.metrics span{color:var(--muted);font-size:13px}.update-main{align-self:start}.update-main dl{margin:0 0 14px}
    .app-shell{grid-template-columns:104px 1fr;grid-template-rows:76px minmax(0,1fr)}.topbar{height:76px;padding:0 28px;border-color:#e7ebe6}.brand strong{font-size:27px}.rail{padding:24px 10px 18px;border-color:#e7ebe6}.nav-item{min-height:78px;border-radius:8px;font-size:15px;gap:7px}.nav-item.active:before{left:-10px;width:4px}.workspace{background:#fffefa}.content-grid{grid-template-columns:300px minmax(0,1fr) 464px;gap:16px;padding:16px 22px 10px;overflow:auto}.content-grid.model-setup-layout{grid-template-columns:300px minmax(0,1fr) 500px;gap:34px;padding:28px 34px 12px}.content-grid.book-creation-layout{grid-template-columns:300px minmax(0,1fr) 508px;gap:34px;padding:28px 34px 12px}.content-grid.first-launch-layout{grid-template-columns:minmax(600px,1fr) 572px;gap:36px;padding:20px 48px 0}.content-grid.blueprint-layout{grid-template-columns:300px minmax(0,1fr);align-items:start}.content-grid.canon-gate-layout{grid-template-columns:300px minmax(0,1fr) 420px}.content-grid.production-layout,.content-grid.human-review-layout{grid-template-columns:300px minmax(0,1fr) 420px}.content-grid.human-review-layout{grid-template-columns:300px minmax(0,1fr) 620px}.main-panel,.right-panel,.side-panel,.reader-panel,.project-context,.launch-card,.data-card,.table-card,.proposal-card,.quality-card{border-color:#e4e9e4;border-radius:8px;box-shadow:none;background:#fffefa}.project-context{padding:24px 26px;gap:22px;border-left:0;border-top:0;border-bottom:0;border-radius:0}.project-identity{grid-template-columns:120px 1fr;gap:18px}.project-cover{width:120px;border-radius:9px;background:linear-gradient(145deg,#25372f,#799078)}.forest-cover{background:radial-gradient(circle at 58% 22%,rgba(250,247,223,.7),transparent 20%),radial-gradient(circle at 35% 40%,rgba(42,67,54,.8),transparent 26%),linear-gradient(145deg,#1f332b,#83927e 62%,#d2d7c7)}.project-identity h2{font-size:23px}.project-context h3{font-size:18px;color:var(--ink);margin-top:20px}.chapter-row{min-height:44px;border-bottom:1px solid #eef1ec;border-radius:7px;color:#303832}.chapter-row span{font-weight:700}.chapter-row.active{box-shadow:inset 4px 0 0 var(--accent)}.top-actions{gap:22px}.notification-link{position:relative}.notification-badge{position:absolute;right:-8px;top:-10px;min-width:20px;height:20px;border-radius:999px;background:#e12c27;color:#fff;font-size:12px;font-weight:800;display:grid;place-items:center}.author-menu{display:flex;align-items:center;gap:10px;font-weight:650}.author-avatar{width:38px;height:38px;border-radius:999px;background:linear-gradient(160deg,#26332f,#f1d7cf 45%,#222)}
    .content-grid:not(.first-launch-layout)+.pipeline{flex:0 0 108px;min-height:108px;margin:0 22px 14px;padding:12px 20px 10px;grid-template-columns:minmax(0,1fr);gap:8px}.content-grid:not(.first-launch-layout)+.pipeline h2{font-size:17px}.content-grid:not(.first-launch-layout)+.pipeline-track{grid-column:1 / -1;gap:10px}.content-grid:not(.first-launch-layout)+.pipeline-step{width:98px;gap:2px}.content-grid:not(.first-launch-layout)+.pipeline-icon{width:34px;height:34px;font-size:17px}.content-grid:not(.first-launch-layout)+.pipeline-connector{flex:0 1 88px;min-width:42px;margin-top:16px}.content-grid:not(.first-launch-layout)+.pipeline-step strong{font-size:14px}.content-grid:not(.first-launch-layout)+.pipeline-step em{font-size:12px;line-height:1.2}
    .setup-guide{display:grid;gap:58px;align-content:start;padding:116px 0 0}.setup-guide-card{position:relative;border:1px solid #eadfcc;border-radius:8px;background:#fffdf8;padding:18px 18px 18px 54px;min-height:146px}.setup-guide-card span{position:absolute;left:18px;top:20px;width:24px;height:24px;border-radius:999px;background:var(--accent);color:#fff;display:grid;place-items:center;font-weight:800}.setup-guide-card h2{font-size:18px}.model-config-panel{padding:8px 0;background:transparent;border:0}.model-config-panel .panel-head h1,.book-creation-main .panel-head h1{font-size:34px}.model-config-form{border:0;background:transparent;padding:18px 0 0;gap:24px}.model-credential-section{gap:16px}.model-credential-section h3{font-size:18px}.model-field{grid-template-columns:170px minmax(0,1fr);gap:22px}.model-field label{font-size:18px}.input-shell,.select-shell{min-height:56px;border-radius:7px}.advanced-model-options{margin-left:192px;border:1px solid var(--line);border-radius:8px;padding:14px;background:#fff}.advanced-model-options summary{width:max-content;list-style:none}.advanced-model-options summary::-webkit-details-marker{display:none}.advanced-model-section{display:grid;gap:14px;border-top:1px solid var(--line);padding-top:18px;margin-top:16px}.advanced-model-section h3{margin:0;color:var(--ink);font-size:16px}.model-actions{border-top:0;justify-content:flex-start;margin-left:192px}.setup-aside{gap:24px}.setup-aside section,.generation-card,.hint-box{border:1px solid #e4e9e4;border-radius:8px;background:#fffefa}.setup-aside section{padding:24px}.setup-checklist li{grid-template-columns:30px 1fr;min-height:48px}.local-database-card .db-path{border:1px solid var(--line);border-radius:7px;padding:12px;background:#fff}
    .book-wizard{padding:28px}.vertical-flow{counter-reset:wizard;list-style:none;padding:0;margin:42px 0;display:grid;gap:24px}.vertical-flow li{counter-increment:wizard;display:grid;grid-template-columns:42px 1fr;gap:18px;align-items:center}.vertical-flow li:before{content:counter(wizard);width:42px;height:42px;border-radius:999px;border:1px solid var(--line);display:grid;place-items:center;font-weight:800}.vertical-flow .active{background:var(--accent-2);border-radius:8px;padding:14px}.vertical-flow strong{display:block}.vertical-flow span{grid-column:2;color:var(--muted)}.book-creation-main{padding:28px 36px}.idea-field{position:relative;font-size:16px;color:var(--ink);font-weight:650}.idea-field textarea{min-height:112px;font-size:19px;line-height:1.6;padding-right:84px}.idea-counter{position:absolute;right:18px;bottom:16px;color:var(--muted);font-weight:400}.generated-preview{padding:26px}.generation-card-list{display:grid;gap:16px}.generation-card{min-height:86px;display:grid;grid-template-columns:52px 1fr;align-items:center;padding:16px 18px}.generation-card>span{width:42px;height:42px;border:1px solid var(--line);border-radius:8px;display:grid;place-items:center;color:var(--accent)}.generation-card strong{font-size:18px}.hint-box{padding:16px;color:var(--muted)}
    .proposal-grid{grid-template-columns:repeat(3,minmax(220px,1fr));gap:18px}.proposal-choice-card{min-height:220px;padding:20px;border-color:#e3e9e4;cursor:pointer;align-content:start}.proposal-choice-card.selected{border:2px solid var(--accent);background:#f8fbf6}.proposal-choice-card:hover{border-color:var(--accent)}.proposal-choice-card header h3{font-size:22px}.proposal-title{font-size:20px}.proposal-choice-card p{margin:0}.proposal-choice-card p span{display:block;color:var(--muted);font-size:12px}.proposal-preview-list{display:flex;gap:8px;flex-wrap:wrap}.proposal-preview-list span{border:1px solid var(--line);border-radius:999px;padding:4px 8px;background:#fff;color:var(--accent);font-size:12px}.blueprint-selected-detail{margin-top:18px}.blueprint-detail-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:14px}.blueprint-detail-heading h2{font-size:24px}.candidate-status-banner{font-size:16px;background:#fff4e8;color:#fa7a0a}.blueprint-actions{padding:22px;display:grid;gap:16px}.blueprint-action-grid{display:grid;grid-template-columns:minmax(280px,360px) minmax(0,1fr);gap:16px;align-items:start}.candidate-confirmation{border:1px solid var(--accent);border-radius:8px;padding:18px;background:#f8fbf6}.blueprint-revision-form{border:1px solid var(--line);border-radius:8px;padding:18px;background:#fff;margin-top:0}.selected-title-summary{font-size:18px;color:var(--ink);font-weight:800}.choice{min-height:54px}.main-panel,.right-panel,.side-panel,.reader-panel,.project-context,.data-card,.table-card,.proposal-card,.quality-card{min-width:0}.canon-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.canon-summary-card{position:relative;border:1px solid #e4e9e4;border-radius:8px;background:#fff;padding:18px 18px 18px 62px;min-height:124px;min-width:0;overflow-wrap:anywhere}.canon-summary-card .card-icon{position:absolute;left:20px;top:22px;color:var(--accent);font-size:24px}.canon-summary-card h2{font-size:19px}.canon-summary-card strong{font-size:22px}.canon-summary-card b{position:absolute;right:18px;top:30px;color:var(--muted)}.canon-summary-card.missing{border-color:#f1d1a2;background:#fffaf0}.canon-completion-gate{border:1px solid #f1d1a2;border-radius:8px;background:#fffaf0;padding:18px;margin-bottom:18px}.canon-completion-gate:not(.trusted){position:sticky;top:0;z-index:5;box-shadow:0 10px 24px rgba(29,40,34,.08)}.canon-completion-gate.trusted{border-color:#c9dac8;background:#f8fbf6}.canon-completion-gate ul{display:flex;gap:8px;flex-wrap:wrap;padding:0;margin:10px 0 14px;list-style:none}.canon-completion-gate li{border:1px solid #ecd1a9;border-radius:999px;background:#fff;padding:5px 10px;color:#8c5a12}.canon-completion-form{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.canon-revision-preview{border:1px solid #c9dac8;border-radius:8px;background:#f8fbf6;padding:18px;margin:0 0 18px;display:grid;gap:14px}.canon-preview-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.canon-preview-head h2{font-size:22px;margin-bottom:8px}.canon-preview-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.canon-preview-summary span{border:1px solid #dce6d9;border-radius:8px;background:#fff;padding:10px 12px;min-width:0}.canon-preview-summary strong{display:block;color:var(--ink);font-size:13px;margin-bottom:4px}.canon-preview-summary em{display:block;font-style:normal;color:var(--muted);overflow-wrap:anywhere}.canon-preview-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.canon-preview-actions form{margin:0}.canon-preview-actions button{min-width:160px}.canon-preview-sections{display:grid;gap:12px}.canon-preview-section{border:1px solid #e4e9e4;border-radius:8px;background:#fff;padding:14px;overflow-wrap:anywhere}.canon-preview-section header{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px}.canon-preview-section h3{margin:0;color:var(--ink);font-size:16px}.canon-preview-section header span{font-size:13px;color:var(--muted)}.canon-preview-section .value-list{margin:0;padding-left:18px}.chapter-preview-list{list-style:none;margin:0;padding:0;display:grid;gap:10px}.chapter-preview-list li{border-bottom:1px solid var(--line);padding-bottom:10px}.chapter-preview-list li:last-child{border-bottom:0;padding-bottom:0}.chapter-preview-list strong{display:block;color:var(--ink);margin-bottom:4px}.canon-gate-main .canon-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.canon-gate-main .detail-state-sections{grid-template-columns:1fr}.canon-section-panel{scroll-margin-top:170px;overflow-wrap:anywhere}.canon-section-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap}.canon-section-head>div{min-width:0}.canon-section-lock{display:flex;gap:8px;align-items:center;justify-content:flex-start;flex-wrap:wrap}.canon-revision-details{margin-top:12px}.canon-revision-details summary{cursor:pointer;color:var(--accent);font-weight:800}.chapter-production-basis{margin-top:18px}.detail-state-sections{margin-top:18px}.canon-gate-layout .right-panel{position:sticky;top:0;align-self:start;max-height:calc(100vh - 102px);overflow:auto}.audit-risk-panel section,.completion-aside section,.cockpit-aside section,.production-aside section{border:1px solid #e4e9e4;border-radius:8px;background:#fff;padding:18px}.lock-confirmation{background:#fffaf0!important;border-color:#f1d1a2!important}.gate-actions{display:grid;grid-template-columns:1fr;gap:12px}.project-cockpit,.project-progress-overview{padding:26px}.progress-metrics{grid-template-columns:repeat(4,1fr)}.progress-metrics em{display:block;color:var(--muted);font-style:normal}.cockpit-aside,.completion-aside{display:grid;gap:18px;align-content:start}.completion-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}
    .blueprint-context .project-identity{grid-template-columns:120px 1fr}.blueprint-step-list{display:grid;gap:12px}.blueprint-step{display:grid;grid-template-columns:30px 1fr auto;align-items:center;gap:12px;min-height:52px;border-radius:8px;color:#6c746f}.blueprint-step span{width:28px;height:28px;border-radius:999px;border:2px solid #cbd2ce;display:grid;place-items:center;font-weight:800}.blueprint-step.done span{border-color:var(--accent);background:var(--accent);color:#fff}.blueprint-step.active{background:#fff9ef;color:#202823;box-shadow:inset 4px 0 0 #ff8a17;padding:0 10px}.blueprint-step.active span{border-color:#ff8a17;color:#ff8a17;background:#fff}.blueprint-step em{font-style:normal;border:1px solid var(--line);border-radius:7px;padding:4px 8px;background:#fff;font-size:13px}.blueprint-generating-timeline{border:1px solid var(--line);border-radius:8px;background:#fff;display:grid;margin-top:36px}.blueprint-generating-timeline article{display:grid;grid-template-columns:44px 1fr auto;gap:18px;align-items:center;min-height:120px;padding:18px 28px;border-bottom:1px solid var(--line)}.blueprint-generating-timeline article:last-child{border-bottom:0}.blueprint-generating-timeline span{width:36px;height:36px;border-radius:999px;border:2px solid #9ba7a1;display:grid;place-items:center}.blueprint-generating-timeline .done span{background:var(--accent);color:#fff;border-color:var(--accent)}.blueprint-generating-timeline .current{background:#fffaf2;outline:1px solid #f5bf76}.blueprint-generating-timeline .current span{border-color:#ff8a17;color:#ff8a17}.loading-wave{letter-spacing:10px;color:#f4a247}.generation-task-list{display:grid;gap:16px}.generation-task-list p{display:flex;align-items:center;justify-content:space-between;gap:18px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:18px;margin:0}.generation-task-list span{color:var(--muted)}
    .production-main{padding:24px}.chapter-production-layout .reader-panel,.human-review-layout .reader-panel{border-radius:8px}.chapter-task-board{display:grid;gap:18px}.chapter-stage-chain{display:flex;gap:12px;align-items:stretch;flex-wrap:wrap}.chapter-stage-link{width:28px;min-width:28px;height:2px;background:linear-gradient(90deg,#d8ddd3 0%,#c7d6c9 100%);align-self:center}.chapter-stage{flex:1 1 180px;display:grid;gap:8px;padding:16px;border:1px solid var(--line);border-radius:12px;background:#fff}.chapter-stage span{display:grid;place-items:center;width:30px;height:30px;border-radius:999px;border:1px solid currentColor;font-weight:800}.chapter-stage strong{font-size:15px}.chapter-stage em{font-style:normal;font-size:12px}.chapter-stage.done{color:var(--accent);background:#f7fbf7}.chapter-stage.current{color:var(--warn);background:#fff8ef;border-color:#efd2a7}.chapter-stage.pending{color:var(--muted)}.chapter-result-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.chapter-result-slot{border:1px solid var(--line);border-radius:12px;background:#fff;padding:16px;display:grid;gap:10px;min-height:174px;min-width:0}.chapter-result-slot.ready{background:#fbfdf9}.chapter-result-slot.pending{background:#f8f6ef}.chapter-result-slot header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}.chapter-result-slot header strong{font-size:16px}.chapter-result-slot header span{font-size:12px;color:var(--muted)}.chapter-slot-preview{min-width:0}.chapter-slot-preview p,.chapter-slot-preview ul,.chapter-slot-preview dl{margin:0}.chapter-slot-preview ul{padding-left:18px}.chapter-slot-preview dl{display:grid;grid-template-columns:76px 1fr;gap:6px 10px}.production-grid{grid-template-columns:1.15fr 1.45fr 1fr 1fr;gap:16px}.production-grid .data-card:nth-child(5),.production-grid .data-card:nth-child(6){grid-column:span 2}.review-decision-surface{display:grid;gap:18px}.review-summary-stack{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:8px}.review-summary-card{padding:16px 18px;border:1px solid var(--line);border-radius:12px;background:var(--panel-elevated);min-width:0}.review-summary-card h2{margin-bottom:8px}.review-summary-card p:last-child{margin-bottom:0}.decision-question-list{display:grid;gap:8px;padding-left:18px;margin:0}.decision-question-list li{margin:0;line-height:1.6}.state-change-pill{display:inline-flex;align-items:center;padding:4px 8px;margin-right:8px;border-radius:999px;background:var(--accent-2);color:var(--accent-strong);font-size:12px;font-weight:700}.human-review-layout .chapter-text{font-size:20px;line-height:2.18;min-height:540px;border-top:1px solid var(--line);padding:24px 34px}.review-decision-panel{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.review-repair-form{grid-column:1 / -1}.review-repair-form textarea{min-height:124px}.review-tabs{grid-template-columns:repeat(4,1fr);margin:0 0 18px}.review-list li{border-radius:0;border-left:0;border-right:0;border-top:0}
    .content-grid.workspace-focus-layout{grid-template-columns:300px minmax(0,1fr) 420px;align-items:start}.workspace-focus-card{display:grid;gap:20px;padding:28px 30px;border-radius:12px}.workspace-focus-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.workspace-current-task{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;padding:18px 20px;border:1px solid #d8e3d7;border-radius:12px;background:linear-gradient(180deg,#f7fbf7 0%,#fffdf8 100%)}.workspace-current-task strong{display:block;font-size:18px;color:var(--ink);margin-bottom:6px}.workspace-primary-action{display:grid;align-content:center}.workspace-primary-action .button,.workspace-primary-action form{margin:0}.workspace-kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.workspace-kpi-grid article{border:1px solid var(--line);border-radius:10px;background:#fff;padding:14px}.workspace-kpi-grid strong{display:block;font-size:28px;color:var(--ink)}.workspace-kpi-grid span{font-size:13px;color:var(--muted)}.workspace-foundation-panel{display:grid;gap:14px}.workspace-section-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.workspace-section-head span{font-size:13px;color:var(--muted)}.workspace-foundation-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.workspace-snapshot-card,.workspace-volume-plan{border:1px solid var(--line);border-radius:12px;background:#fff;padding:16px}.workspace-snapshot-card strong,.workspace-volume-plan strong{display:block;margin-bottom:8px;font-size:15px;color:var(--ink)}.workspace-snapshot-card p,.workspace-volume-plan p{margin:0}.workspace-result-sidebar{display:grid;gap:16px;align-content:start}.workspace-result-section{border:1px solid #e4e9e4;border-radius:12px;background:#fff;padding:18px;display:grid;gap:14px}.workspace-trace-row{display:grid;grid-template-columns:56px 1fr;gap:12px;align-items:center;padding:12px 14px;border:1px solid var(--line);border-radius:10px;background:#fbfcf8}.workspace-trace-row strong{font-size:16px;color:var(--ink)}.workspace-trace-row span{color:var(--muted)}.workspace-mini-list{list-style:none;margin:0;padding:0;display:grid;gap:10px}.workspace-mini-list li{display:grid;gap:4px;padding-bottom:10px;border-bottom:1px solid var(--line)}.workspace-mini-list li:last-child{padding-bottom:0;border-bottom:0}.workspace-mini-list strong{font-size:13px;color:var(--ink)}.workspace-action-list{display:grid;gap:10px}.content-grid.home-focus-layout{grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr);gap:20px;padding:24px 28px 12px;align-items:start}.current-focus-card,.open-book-focus-panel{padding:24px 28px;border-radius:12px}.current-focus-card{display:grid;gap:18px}.section-kicker{margin:0 0 10px;color:var(--accent-strong);font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.focus-checklist{display:grid;gap:8px;padding:16px 18px;border:1px solid var(--line);border-radius:10px;background:var(--panel-soft)}.focus-checklist p{margin:0}.focus-checklist strong{color:var(--ink)}.ai-result-timeline{display:grid;gap:12px;align-content:start}.timeline-stack,.timeline-section{display:grid;gap:12px}.timeline-row{display:grid;gap:4px;padding:12px 14px;background:var(--panel-muted,var(--panel-soft));border:1px solid var(--line);border-radius:10px}.timeline-row strong{font-size:16px}.timeline-row span{color:var(--muted)}.step-rail{align-content:start}.open-book-focus-panel{display:grid;gap:18px}.single-focus-form{display:grid;gap:16px}.single-focus-form .actions{padding-top:4px}.optional-inputs{border:1px solid var(--line);border-radius:10px;background:var(--panel-soft)}.optional-inputs summary{cursor:pointer;padding:12px 14px;font-weight:700;color:var(--ink)}.optional-inputs summary::-webkit-details-marker{display:none}.optional-input-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:0 14px 14px}.open-book-preview{align-content:start}.open-book-preview h2{margin-bottom:8px}.open-book-preview p{margin-bottom:0}.open-book-focus-panel .idea-field{font-size:16px;color:var(--ink);font-weight:700}.open-book-focus-panel .idea-field textarea{min-height:180px;font-size:20px;line-height:1.7;padding:16px 18px}
    @media(max-width:1100px){.app-shell{grid-template-columns:82px minmax(0,1fr)}.brand strong{font-size:18px}.rail strong{font-size:13px}.global-status-strip{grid-template-columns:minmax(0,1fr);padding:12px}.content-grid,.first-launch-layout,.blueprint-layout,.content-grid.model-setup-layout,.content-grid.canon-gate-layout,.content-grid.production-layout,.content-grid.workspace-focus-layout{grid-template-columns:minmax(0,1fr)}.empty-hero,.reader-panel,.blueprint-actions{grid-column:auto}.blueprint-action-grid{grid-template-columns:minmax(0,1fr)}.form-grid,.card-grid,.state-sections,.blueprint-detail-grid,.proposal-grid,.split,.quality-grid,.canon-state-grid,.canon-summary-grid,.production-grid,.production-stage-grid,.impact-scope>div,.canon-preview-summary,.optional-input-grid,.workspace-foundation-grid,.workspace-kpi-grid,.chapter-result-grid,.chapter-stage-chain,.review-summary-stack,.review-decision-panel{grid-template-columns:minmax(0,1fr)}.workspace-current-task{grid-template-columns:minmax(0,1fr)}.model-field{grid-template-columns:minmax(0,1fr)}.model-field p{grid-column:auto}.model-check,.advanced-model-options{margin-left:0}.top-actions{display:none}.content-grid{padding:12px;overflow-x:hidden}.canon-gate-layout .right-panel{position:static;max-height:none;overflow:visible}.canon-completion-gate:not(.trusted){top:0}.canon-summary-card{padding-right:42px}.canon-preview-head{display:grid}.canon-preview-actions button{width:100%}.pipeline{grid-template-columns:minmax(0,1fr);margin:0 18px 18px;flex-basis:auto;min-height:180px}.pipeline-track{grid-column:1}.project-identity{grid-template-columns:64px minmax(0,1fr)}.project-cover{width:64px}.first-launch-layout{padding:18px}.first-launch-hero{min-height:420px;padding-top:42px}.launch-actions{width:min(360px,100%)}}
    """
