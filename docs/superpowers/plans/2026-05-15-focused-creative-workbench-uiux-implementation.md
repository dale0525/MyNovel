# Focused Creative Workbench UI/UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild MyNovel's primary product surfaces into a tighter, eye-friendly "Focused Creative Workbench" that makes the current task, AI progress, AI self-repair, and required user decisions explicit across home, open-book, chapter production, and chapter review flows.

**Architecture:** Keep the server-rendered HTML approach, but move repeated UI patterns into small view helpers so the main page functions stop accreting string templates. Implement the redesign in layers: first add shared shell/status components and design tokens, then refit home/open-book/workspace/review surfaces onto those shared primitives, and finish with regression coverage that locks in the new copy and structure.

**Tech Stack:** Python 3.12, server-rendered HTML strings, `pytest` via `pixi`, existing `mynovel` view modules and i18n catalog

---

## File Structure

### Existing files to modify

- `src/mynovel/ui_shell.py`
  - Owns the shared app shell and global CSS.
  - Will absorb the new visual tokens, tighter spacing, persistent status strip container, and shared utility classes.
- `src/mynovel/home_views.py`
  - Owns empty-home and project-home surfaces.
  - Will be reshaped into a next-action dashboard instead of a broad overview.
- `src/mynovel/product_views.py`
  - Owns `render_home`, `render_new_book_page`, `render_book_workspace`, and `render_chapter_review`.
  - Needs decomposition because it is already 904 lines and this redesign will otherwise push it over the repo’s 1000-line limit.
- `src/mynovel/product_components.py`
  - Already contains reusable product-side panels.
  - Will host tighter side cards and running-stage summary helpers after extraction from `product_views.py`.
- `src/mynovel/chapter_review_views.py`
  - Owns the current right-side review inspector.
  - Will be reworked into a result-first review surface with structured "what changed / what AI fixed / what you decide" sections.
- `src/mynovel/i18n.py`
  - Needs new Chinese copy for current-task cards, AI status summaries, result labels, and decision prompts.
- `tests/test_product_ui.py`
  - Primary coverage for rendered HTML across home, workspace, production, and review pages.
- `tests/test_chapter_review_ui.py`
  - Primary coverage for the review inspector/review surface details.
- `tests/test_product_regressions.py`
  - Secondary coverage for copy regressions and UX framing language.
- `tests/test_dev_server.py`
  - Route-level rendering checks for home and chapter views.

### New files to create

- `src/mynovel/ui_status_views.py`
  - Shared helpers for global AI status strip, current-task summary cards, and calm segmented progress markup.
- `src/mynovel/workspace_views.py`
  - Extract workspace-focused render helpers from `product_views.py` so `product_views.py` stays under 1000 lines.
- `src/mynovel/open_book_views.py`
  - Extract open-book page sections and guided-step helpers from `product_views.py`.

### Why this split

- The redesign introduces repeated "current task / AI status / next decision" patterns. Duplicating them inline across `home_views.py`, `product_views.py`, and `chapter_review_views.py` would make future tuning expensive.
- `product_views.py` is already close to the line limit; extracting open-book and workspace helpers avoids violating the repository rule while keeping page entry points stable.

---

### Task 1: Build Shared Shell Tokens And Status Components

**Files:**
- Create: `src/mynovel/ui_status_views.py`
- Modify: `src/mynovel/ui_shell.py`
- Modify: `src/mynovel/i18n.py`
- Test: `tests/test_product_ui.py`

- [ ] **Step 1: Write the failing shell/status tests**

Add focused assertions to `tests/test_product_ui.py` that lock in the new shell primitives without requiring any page-specific redesign yet:

```python
def test_application_shell_exposes_global_ai_status_strip() -> None:
    page = render_home(
        Path("/tmp/demo.db"),
        [],
        ProviderConfig(
            llm_base_url="https://example.invalid/v1",
            llm_api_key="sk-demo",
            llm_model="gpt-4.1-mini",
            embedding_use_llm_credentials=True,
            embedding_base_url="",
            embedding_model="text-embedding-3-small",
            rerank_use_llm_credentials=True,
        ),
    )

    assert "global-status-strip" in page
    assert "你现在要做" in page
    assert "AI 正在做" in page
    assert "完成后你要决定" in page


def test_application_shell_uses_focused_workbench_design_tokens() -> None:
    page = render_home(Path("/tmp/demo.db"), [], None)

    assert "--bg-canvas:" in page
    assert "--panel-elevated:" in page
    assert "--accent-strong:" in page
    assert "app-shell-compact" in page
```

- [ ] **Step 2: Run the targeted shell test to verify it fails**

Run:

```bash
pixi run pytest tests/test_product_ui.py::test_application_shell_exposes_global_ai_status_strip -v
```

Expected: FAIL because `render_app_page()` does not render `global-status-strip` yet.

- [ ] **Step 3: Add the shared status helpers**

Create `src/mynovel/ui_status_views.py` with small pure render helpers that can be called from multiple page modules:

```python
from __future__ import annotations

import html
from dataclasses import dataclass


@dataclass(frozen=True)
class StatusStage:
    label: str
    state: str


def render_global_status_strip(
    *,
    current_task: str,
    ai_status: str,
    next_decision: str,
    stages: list[StatusStage] | None = None,
) -> str:
    stage_markup = ""
    if stages:
        stage_markup = (
            '<ol class="status-stage-list">'
            + "".join(
                f'<li class="status-stage {html.escape(stage.state)}">{html.escape(stage.label)}</li>'
                for stage in stages
            )
            + "</ol>"
        )
    return f'''
      <section class="global-status-strip" aria-label="当前 AI 状态">
        <div><span>你现在要做</span><strong>{html.escape(current_task)}</strong></div>
        <div><span>AI 正在做</span><strong>{html.escape(ai_status)}</strong></div>
        <div><span>完成后你要决定</span><strong>{html.escape(next_decision)}</strong></div>
        {stage_markup}
      </section>
    '''
```

- [ ] **Step 4: Wire the shell to use the new helpers and tokens**

Update `src/mynovel/ui_shell.py` so the app shell always has a status-strip slot and the CSS tokens reflect the new design system:

```python
from mynovel.ui_status_views import StatusStage, render_global_status_strip


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
    status_markup = status_strip or default_status_strip()
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
    <header class="topbar"><a class="brand" href="/">MyNovel</a></header>
    <main class="workspace app-shell-compact">
      {status_markup}
      {f"<p class='notice'>{html.escape(message)}</p>" if message else ""}
      <div class="{html.escape(content_class, quote=True)}">{main}</div>
      {bottom}
    </main>
  </div>
</body>
</html>
"""


def default_status_strip() -> str:
    return render_global_status_strip(
        current_task="查看当前项目的下一步",
        ai_status="等待你选择或触发下一步操作",
        next_decision="进入当前最需要推进的页面",
        stages=[
            StatusStage("输入", "done"),
            StatusStage("执行", "idle"),
            StatusStage("汇报", "idle"),
            StatusStage("决策", "idle"),
        ],
    )
```

Update `app_css()` to introduce compact workbench tokens and classes:

```css
:root{
  --bg-canvas:#f3f1ea;
  --bg-wash:#ece9df;
  --panel-elevated:#fbfaf5;
  --panel-muted:#f5f3ec;
  --ink-strong:#1f2a24;
  --ink-soft:#637168;
  --accent-strong:#3f6a4d;
  --accent-soft:#e7efe4;
  --progress-warm:#b8843f;
}
.workspace.app-shell-compact{background:linear-gradient(180deg,var(--bg-canvas),var(--bg-wash))}
.global-status-strip{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:12px;
  margin:16px 22px 0;
  padding:14px 16px;
  border:1px solid var(--line);
  border-radius:12px;
  background:rgba(251,250,245,.92);
}
.status-stage-list{display:flex;gap:8px;list-style:none;padding:0;margin:4px 0 0}
```

- [ ] **Step 5: Add the required i18n keys**

Extend `src/mynovel/i18n.py` with reusable labels rather than hardcoding them everywhere later:

```python
"status.current_task": "你现在要做",
"status.ai_working": "AI 正在做",
"status.next_decision": "完成后你要决定",
"status.stage_input": "输入",
"status.stage_execute": "执行",
"status.stage_report": "汇报",
"status.stage_decide": "决策",
```

- [ ] **Step 6: Run the targeted shell tests to verify they pass**

Run:

```bash
pixi run pytest tests/test_product_ui.py::test_application_shell_exposes_global_ai_status_strip tests/test_product_ui.py::test_application_shell_uses_focused_workbench_design_tokens -v
```

Expected: PASS for both tests.

- [ ] **Step 7: Commit the shared shell layer**

```bash
git add src/mynovel/ui_status_views.py src/mynovel/ui_shell.py src/mynovel/i18n.py tests/test_product_ui.py
git commit -m "feat: add focused workbench shell status strip"
```

---

### Task 2: Redesign Home And Open-Book Into Single-Task Flows

**Files:**
- Create: `src/mynovel/open_book_views.py`
- Modify: `src/mynovel/home_views.py`
- Modify: `src/mynovel/product_views.py`
- Modify: `src/mynovel/ui_shell.py`
- Modify: `src/mynovel/i18n.py`
- Test: `tests/test_product_ui.py`
- Test: `tests/test_product_regressions.py`
- Test: `tests/test_dev_server.py`

- [ ] **Step 1: Write the failing home/open-book tests**

Add tests that capture the redesigned product intent:

```python
def test_home_page_prioritizes_single_next_action_card() -> None:
    page = render_home(
        Path("/tmp/demo.db"),
        [book],
        configured_provider,
        [],
    )

    assert "current-focus-card" in page
    assert "当前最该推进" in page
    assert "最近 AI 结果" in page
    assert "信息汇总" not in page


def test_new_book_page_keeps_idea_as_the_only_required_primary_input() -> None:
    page = render_new_book_page(configured_provider)

    assert "一句话写下这本书最想写什么" in page
    assert "可选补充" in page
    assert "系统将生成什么" in page
    assert 'name="idea"' in page
```

Add one route-level smoke assertion to `tests/test_dev_server.py`:

```python
def test_home_page_renders_focused_next_action_language() -> None:
    page = render_home(tmp_db_path, [book], provider_config, [])
    assert "你现在只需要做什么" in page
```

- [ ] **Step 2: Run the focused home/open-book tests to verify they fail**

Run:

```bash
pixi run pytest \
  tests/test_product_ui.py::test_home_page_prioritizes_single_next_action_card \
  tests/test_product_ui.py::test_new_book_page_keeps_idea_as_the_only_required_primary_input \
  tests/test_dev_server.py::test_home_page_renders_focused_next_action_language -v
```

Expected: FAIL because the current home and open-book layouts still use the older dashboard and wizard copy.

- [ ] **Step 3: Extract open-book helper sections so `product_views.py` stays below 1000 lines**

Create `src/mynovel/open_book_views.py` with helpers for the redesigned flow:

```python
from __future__ import annotations

import html
from typing import Sequence


def render_open_book_focus_panel(locale: str) -> str:
    return """
      <section class="main-panel open-book-focus-panel">
        <div class="panel-head">
          <div>
            <p class="section-kicker">当前任务</p>
            <h1>一句话写下这本书最想写什么</h1>
            <p>先给核心灵感，其他信息都可以作为可选补充。</p>
          </div>
          <span class="status-pill trusted">当前只做一件事</span>
        </div>
      </section>
    """


def render_open_book_optional_fields(
    genre_options: Sequence[str],
    audience_options: Sequence[str],
    default_target_words: int,
    default_chapter_words: int,
) -> str:
    genre_select = "".join(
        f"<option value='{html.escape(item)}'>{html.escape(item)}</option>"
        for item in genre_options
    )
    audience_select = "".join(
        f"<option value='{html.escape(item)}'>{html.escape(item)}</option>"
        for item in audience_options
    )
    return f"""
      <details class="optional-inputs">
        <summary>可选补充</summary>
        <div class="optional-input-grid">
          <label>题材<select name="genre"><option value="">交给 AI 判断</option>{genre_select}</select></label>
          <label>读者<select name="audience"><option value="">交给 AI 判断</option>{audience_select}</select></label>
          <label>目标总字数<input name="target_word_count" type="number" value="{default_target_words}"></label>
          <label>单章目标字数<input name="chapter_word_count" type="number" value="{default_chapter_words}"></label>
        </div>
      </details>
    """
```

- [ ] **Step 4: Rewrite the empty and project home surfaces around a single "next action" card**

Refit `src/mynovel/home_views.py` so both `render_empty_home()` and `render_project_home()` align to the new structure:

```python
def render_project_home(
    books: list[Book],
    blueprints: list[OpenBookBlueprint],
    configured: bool,
    locale: str = DEFAULT_LOCALE,
) -> str:
    rows = "".join(
        f"<a class='timeline-row' href='/book/{book.id}'><strong>{html.escape(book.title)}</strong><span>{_book_status_label(book.status, locale)}</span></a>"
        for book in books
    )
    return f"""
      <section class="main-panel current-focus-card">
        <div class="panel-head">
          <div>
            <p class="section-kicker">当前最该推进</p>
            <h1>{t("home.workspace_title", locale)}</h1>
            <p>你现在只需要做什么：继续推进当前项目的下一步。</p>
          </div>
          <a class="button" href="/review">进入当前任务</a>
        </div>
        <div class="focus-checklist">
          <p><strong>AI 最近完成了什么</strong></p>
          <p>{model_status}</p>
        </div>
      </section>
      <aside class="right-panel ai-result-timeline">
        <h2>最近 AI 结果</h2>
        <div class="project-list">{rows}{blueprint_entry}</div>
      </aside>
    """
```

For the empty state, change the hero from broad marketing copy to a single-action start card:

```python
<h1>先写下第一本书的核心灵感</h1>
<p>完成这一步后，系统再帮你生成开书方向与可信设定基础。</p>
```

- [ ] **Step 5: Rewrite `render_new_book_page()` to center the one required action**

Update `src/mynovel/product_views.py` to import the new open-book helpers and simplify the page:

```python
from mynovel.open_book_views import (
    render_open_book_focus_panel,
    render_open_book_optional_fields,
    render_open_book_preview_sidebar,
)


def render_new_book_page(
    provider_config: ProviderConfig | None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
):
    main = f"""
      <aside class="side-panel step-rail">
        <h2>开书流程</h2>
        <ol class="step-list vertical-flow">
          <li class="active"><strong>写下核心灵感</strong><span>只先完成这一步</span></li>
          <li><strong>选择 AI 方向</strong><span>比较生成方案后再决定</span></li>
          <li><strong>确认进入生产</strong><span>定盘后再开始章节生产</span></li>
        </ol>
      </aside>
      <section class="main-panel open-book-focus-panel">
        {render_open_book_focus_panel(locale)}
        <form method="post" action="/open-book" class="single-focus-form">
          <label class="idea-field">一句话写下这本书最想写什么
            <textarea name="idea" placeholder="{t('book.idea_placeholder', locale)}" required></textarea>
          </label>
          {render_open_book_optional_fields(GENRE_PRESETS, AUDIENCE_PRESETS, DEFAULT_TARGET_WORD_COUNT, DEFAULT_CHAPTER_WORD_COUNT)}
          <div class="actions">
            <button type="submit"{disabled}>生成开书方案</button>
          </div>
        </form>
      </section>
      {render_open_book_preview_sidebar(locale)}
    """
```

- [ ] **Step 6: Add CSS for the home focus card, AI result timeline, and optional-input drawer**

Update `src/mynovel/ui_shell.py` with the new layout classes:

```css
.current-focus-card,.open-book-focus-panel{padding:24px 28px;border-radius:12px}
.section-kicker{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-soft)}
.ai-result-timeline{display:grid;gap:12px}
.timeline-row{display:grid;gap:4px;padding:12px 14px;background:var(--panel-muted);border-radius:10px}
.optional-inputs{border:1px solid var(--line);border-radius:10px;background:var(--panel-muted)}
.optional-inputs summary{cursor:pointer;padding:12px 14px;font-weight:700}
.single-focus-form{display:grid;gap:16px}
```

- [ ] **Step 7: Run the targeted home/open-book test set**

Run:

```bash
pixi run pytest \
  tests/test_product_ui.py::test_home_page_prioritizes_single_next_action_card \
  tests/test_product_ui.py::test_new_book_page_keeps_idea_as_the_only_required_primary_input \
  tests/test_product_regressions.py::test_new_book_idea_field_is_multiline \
  tests/test_dev_server.py::test_home_page_renders_focused_next_action_language -v
```

Expected: PASS for all four tests.

- [ ] **Step 8: Commit the home/open-book redesign**

```bash
git add src/mynovel/open_book_views.py src/mynovel/home_views.py src/mynovel/product_views.py src/mynovel/ui_shell.py src/mynovel/i18n.py tests/test_product_ui.py tests/test_product_regressions.py tests/test_dev_server.py
git commit -m "feat: redesign home and open book focus flows"
```

---

### Task 3: Redesign Workspace And Running Chapter Views Around Current Task + AI Progress

**Files:**
- Create: `src/mynovel/workspace_views.py`
- Modify: `src/mynovel/product_views.py`
- Modify: `src/mynovel/product_components.py`
- Modify: `src/mynovel/ui_status_views.py`
- Modify: `src/mynovel/ui_shell.py`
- Modify: `src/mynovel/i18n.py`
- Test: `tests/test_product_ui.py`
- Test: `tests/test_dev_server.py`

- [ ] **Step 1: Write the failing workspace/running-chapter tests**

Add assertions that the workspace is a next-action surface and the running chapter page previews AI progress/results:

```python
def test_book_workspace_centers_current_project_action() -> None:
    page = render_book_workspace(book, chapters, canon, [])

    assert "当前项目推进" in page
    assert "AI 最近完成了什么" in page
    assert "你现在只需要做什么" in page
    assert "章节计划总览" in page


def test_running_chapter_page_shows_real_stage_chain_and_result_slots() -> None:
    page = render_chapter_review(book, chapters, running_chapter, canon)

    assert "正在进行的步骤" in page
    assert "生成正文" in page
    assert "检查设定一致性" in page
    assert "修复高置信度问题" in page
    assert "本章完成后会出现" in page
    assert "关键状态变化" in page
```

- [ ] **Step 2: Run the workspace/running-chapter tests to verify they fail**

Run:

```bash
pixi run pytest \
  tests/test_product_ui.py::test_book_workspace_centers_current_project_action \
  tests/test_product_ui.py::test_running_chapter_page_shows_real_stage_chain_and_result_slots -v
```

Expected: FAIL because the workspace still renders a broad cockpit and the running chapter page does not yet expose result slots or the new stage language.

- [ ] **Step 3: Extract workspace helper markup**

Create `src/mynovel/workspace_views.py` to keep workspace cards focused and reusable:

```python
from __future__ import annotations

import html


def render_workspace_focus_card(book, active_chapter, locale: str) -> str:
    next_action = "进入本章审核" if active_chapter and active_chapter.status.value == "awaiting_review" else "开始下一章生成"
    return f"""
      <section class="main-panel workspace-focus-card">
        <p class="section-kicker">当前项目推进</p>
        <h1>{html.escape(book.title)}</h1>
        <p>你现在只需要做什么：{html.escape(next_action)}</p>
      </section>
    """


def render_ai_recent_results(traces, locale: str) -> str:
    if not traces:
        return "<p class='muted'>最近还没有新的 AI 结果。</p>"
    return (
        "<div class='timeline-stack'>"
        + "".join(
            f"<article class='timeline-row'><strong>{html.escape(trace.stage)}</strong><span>{html.escape(trace.status)}</span></article>"
            for trace in traces[:4]
        )
        + "</div>"
    )
```

- [ ] **Step 4: Rebuild `render_book_workspace()` around a single current-task card**

Update `src/mynovel/product_views.py` to replace the broad cockpit body with the extracted focus helpers:

```python
from mynovel.workspace_views import (
    render_workspace_focus_card,
    render_workspace_plan_board,
    render_workspace_result_sidebar,
)


def render_book_workspace(
    book: Book,
    chapters: list[Chapter],
    canon: Canon | None,
    traces: list[RunTrace],
    volume_plans: list[VolumePlan] | None = None,
    message: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> str:
    center = f"""
      {render_workspace_focus_card(book, active_chapter, locale)}
      {render_workspace_plan_board(canon, volume_plans or [], chapters, locale)}
    """
    aside = render_workspace_result_sidebar(book, active_chapter, traces, locale)
```

Use the shared status strip for this page with real next-step copy:

```python
status_strip = render_global_status_strip(
    current_task="确认当前项目的下一步",
    ai_status="等待你触发章节生成或进入审核",
    next_decision="决定继续生产、进入审核，或检查可信设定",
)
```

- [ ] **Step 5: Rebuild the running chapter view into a chapter task board**

Update `src/mynovel/product_components.py` and `src/mynovel/ui_status_views.py` so `render_chapter_production_main()` shows a real stage chain and result placeholders:

```python
def render_chapter_production_main(chapter: Chapter) -> str:
    stages = [
        StatusStage("生成正文", "done"),
        StatusStage("检查设定一致性", "current"),
        StatusStage("检查状态变化", "upcoming"),
        StatusStage("修复高置信度问题", "upcoming"),
        StatusStage("整理待你决定的问题", "upcoming"),
    ]
    return f"""
      <section class="main-panel production-task-board">
        <div class="panel-head">
          <div>
            <p class="section-kicker">正在进行的步骤</p>
            <h1>AI 正在生成第 {chapter.number} 章</h1>
            <p>当前阶段会先完成正文、自检和高置信度修复，再把需要你决定的问题整理出来。</p>
          </div>
          <span class="status-pill pending">执行中</span>
        </div>
        {render_segmented_stage_chain(stages)}
        <section class="pending-result-slots">
          <h2>本章完成后会出现</h2>
          <div class="result-slot-grid">
            <article><strong>本章正文</strong><p>完整候选正文。</p></article>
            <article><strong>关键状态变化</strong><p>只在检测到明显变化时展开。</p></article>
            <article><strong>AI 已自动修复</strong><p>本轮已处理的高置信度问题。</p></article>
            <article><strong>需要你决定</strong><p>低置信度分歧和创作取舍。</p></article>
          </div>
        </section>
      </section>
    """
```

- [ ] **Step 6: Add CSS for the workspace focus board and running chapter slots**

Update `src/mynovel/ui_shell.py`:

```css
.workspace-focus-card,.production-task-board{display:grid;gap:18px}
.pending-result-slots{border-top:1px solid var(--line);padding-top:16px}
.result-slot-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.result-slot-grid article{padding:14px 16px;border-radius:10px;background:var(--panel-muted)}
.status-stage.current{background:rgba(184,132,63,.12);color:var(--progress-warm)}
```

- [ ] **Step 7: Run the workspace and running-chapter test set**

Run:

```bash
pixi run pytest \
  tests/test_product_ui.py::test_book_workspace_centers_current_project_action \
  tests/test_product_ui.py::test_running_chapter_page_shows_real_stage_chain_and_result_slots \
  tests/test_product_ui.py::test_running_chapter_page_matches_stage_control_surface \
  tests/test_dev_server.py::test_home_page_enables_open_book_after_provider_config -v
```

Expected: PASS. The third test guards against losing current production controls while the layout changes.

- [ ] **Step 8: Commit the workspace and running-chapter redesign**

```bash
git add src/mynovel/workspace_views.py src/mynovel/product_views.py src/mynovel/product_components.py src/mynovel/ui_status_views.py src/mynovel/ui_shell.py src/mynovel/i18n.py tests/test_product_ui.py tests/test_dev_server.py
git commit -m "feat: redesign workspace and running chapter task board"
```

---

### Task 4: Rebuild Chapter Review Into Result-First AI Collaboration

**Files:**
- Modify: `src/mynovel/chapter_review_views.py`
- Modify: `src/mynovel/product_views.py`
- Modify: `src/mynovel/ui_status_views.py`
- Modify: `src/mynovel/ui_shell.py`
- Modify: `src/mynovel/i18n.py`
- Test: `tests/test_chapter_review_ui.py`
- Test: `tests/test_product_ui.py`
- Test: `tests/workflows/test_chapter_pipeline.py`

- [ ] **Step 1: Write the failing review/result-first tests**

Add tests that enforce the new result-first structure and the "AI fixed first, user decides later" contract:

```python
def test_review_page_starts_with_result_summary_before_full_body() -> None:
    page = render_chapter_review(book, [chapter], chapter, canon)

    assert "本章完成了什么" in page
    assert "关键状态变化" in page
    assert "AI 已自动修复" in page
    assert "还需要你决定什么" in page


def test_review_page_uses_no_key_change_copy_when_state_delta_is_low_information() -> None:
    chapter.state_delta = {"changes": []}

    page = render_chapter_review(book, [chapter], chapter, canon)

    assert "本章无关键状态变更，主要推进为情节执行与铺垫。" in page
```

Add one workflow-facing coverage point that locks in the assumption that a reviewable chapter still contains `state_delta` and `audit_report`, because the new UI depends on them:

```python
def test_run_chapter_pipeline_prepares_state_delta_and_audit_for_result_first_review(tmp_path) -> None:
    with Session(create_db_and_tables(tmp_path / "review.db")) as session:
        reviewed = run_chapter_pipeline(session, chapter.id)
    assert isinstance(reviewed.audit_report, dict)
    assert isinstance(reviewed.state_delta, dict)
```

- [ ] **Step 2: Run the review tests to verify they fail**

Run:

```bash
pixi run pytest \
  tests/test_chapter_review_ui.py::test_review_page_starts_with_result_summary_before_full_body \
  tests/test_chapter_review_ui.py::test_review_page_uses_no_key_change_copy_when_state_delta_is_low_information \
  tests/workflows/test_chapter_pipeline.py::test_run_chapter_pipeline_prepares_state_delta_and_audit_for_result_first_review -v
```

Expected: the first two tests FAIL because the current inspector starts with tabs and does not render the new summary sections.

- [ ] **Step 3: Add explicit summary helpers to `chapter_review_views.py`**

Introduce small helpers that derive the new result sections from the existing `audit_report`, `state_delta`, and chapter texts:

```python
def _render_completion_summary(chapter: Chapter) -> str:
    summary = chapter.summary.strip() or f"第 {chapter.number} 章候选正文已完成，等待你确认是否接受。"
    return f"<section class='review-summary-card'><h2>本章完成了什么</h2><p>{html.escape(summary)}</p></section>"


def _render_state_change_summary(chapter: Chapter) -> str:
    changes = _visible_state_changes(chapter)
    if not changes:
        return (
            "<section class='review-summary-card'>"
            "<h2>关键状态变化</h2>"
            "<p>本章无关键状态变更，主要推进为情节执行与铺垫。</p>"
            "</section>"
        )
    rows = "".join(
        f"<li><strong>{html.escape(_state_type_label(change.get('type')))}</strong> {html.escape(str(change.get('change') or change.get('detail') or '待人工确认'))}</li>"
        for change in changes[:5]
    )
    return (
        "<section class='review-summary-card'>"
        "<h2>关键状态变化</h2>"
        f"<ul class='decision-question-list'>{rows}</ul>"
        "</section>"
    )


def _render_ai_fixed_summary(chapter: Chapter, locale: str) -> str:
    fixed = [issue for issue in _audit_issues(chapter) if issue.get(\"resolved\")]
    if not fixed:
        return (
            "<section class='review-summary-card'>"
            "<h2>AI 已自动修复</h2>"
            "<p>本轮没有可单独列出的高置信度自动修复项。</p>"
            "</section>"
        )
    rows = "".join(
        f"<li>{html.escape(str(issue.get('title') or '已处理问题'))}</li>"
        for issue in fixed
    )
    return (
        "<section class='review-summary-card'>"
        "<h2>AI 已自动修复</h2>"
        f"<ul class='decision-question-list'>{rows}</ul>"
        "</section>"
    )
```

- [ ] **Step 4: Recompose the review surface so result summaries appear above the full inspector**

Update `render_chapter_review()` in `src/mynovel/product_views.py` so the reader panel becomes a decision-first surface:

```python
main = f"""
  {_render_book_sidebar(book, chapters, locale)}
  <section class="reader-panel review-decision-surface">
    <div class="chapter-toolbar">
      <div>
        <h1>{t("chapter.number", locale, number=chapter.number)} {html.escape(chapter.title)}</h1>
        <p>{_chapter_status_label(chapter.status, locale)} · {t("chapter.word_count", locale, count=chapter.word_count)}</p>
      </div>
      <a class="button secondary" href="/book/{book.id}">{t("action.back_to_project", locale)}</a>
    </div>
    {render_review_decision_summary(chapter, canon, locale, traces or [])}
    {_render_chapter_body(chapter, locale)}
  </section>
  <aside class="right-panel review">
    {render_chapter_review_inspector(chapter, canon, locale, traces or [])}
  </aside>
"""
```

And add a page-specific status strip:

```python
status_strip = render_global_status_strip(
    current_task="先看结果摘要，再决定是否接受本章",
    ai_status="已完成正文生成、自检和高置信度修复",
    next_decision="回答剩余分歧，或直接接受这版正文",
)
```

- [ ] **Step 5: Make the inspector ask for decisions, not open-ended work**

Update the lower action section in `chapter_review_views.py` so it frames remaining work as explicit decisions:

```python
<section class="review-summary-card decision-questions">
  <h2>还需要你决定什么</h2>
  <ul class="decision-question-list">
    <li>主角这次是否需要更早暴露真实意图</li>
    <li>反派信息是否暴露过早</li>
  </ul>
  <p>你也可以补充其他修改意见，但不需要先处理 AI 已自动修复的问题。</p>
</section>
```

If there are no unresolved issues, render:

```python
<p>AI 没有留下高风险分歧；你可以直接接受正文，或补充风格性意见。</p>
```

- [ ] **Step 6: Add CSS for review summary cards and decision prompts**

Update `src/mynovel/ui_shell.py`:

```css
.review-decision-surface{display:grid;gap:18px}
.review-summary-stack{display:grid;gap:12px;margin-bottom:8px}
.review-summary-card{padding:16px 18px;border:1px solid var(--line);border-radius:12px;background:var(--panel-elevated)}
.decision-question-list{display:grid;gap:8px;padding-left:18px}
.state-change-pill{display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:var(--accent-soft)}
```

- [ ] **Step 7: Run the review-focused test set**

Run:

```bash
pixi run pytest \
  tests/test_chapter_review_ui.py \
  tests/test_product_ui.py::test_review_page_exposes_revision_repair_accept_and_export_actions \
  tests/workflows/test_chapter_pipeline.py::test_run_chapter_pipeline_prepares_state_delta_and_audit_for_result_first_review -v
```

Expected: PASS. The full `tests/test_chapter_review_ui.py` run protects the existing tabbed diagnostics while the new result-first layer is added above them.

- [ ] **Step 8: Commit the result-first review redesign**

```bash
git add src/mynovel/chapter_review_views.py src/mynovel/product_views.py src/mynovel/ui_status_views.py src/mynovel/ui_shell.py src/mynovel/i18n.py tests/test_chapter_review_ui.py tests/test_product_ui.py tests/workflows/test_chapter_pipeline.py
git commit -m "feat: redesign chapter review as result-first collaboration"
```

---

### Task 5: Final Copy Pass, Responsive Polish, And Regression Verification

**Files:**
- Modify: `src/mynovel/ui_shell.py`
- Modify: `src/mynovel/home_views.py`
- Modify: `src/mynovel/product_views.py`
- Modify: `src/mynovel/chapter_review_views.py`
- Modify: `src/mynovel/i18n.py`
- Test: `tests/test_product_ui.py`
- Test: `tests/test_product_regressions.py`
- Test: `tests/test_dev_server.py`

- [ ] **Step 1: Add failing regression tests for the final copy rules**

Add targeted copy assertions that protect the spec’s language system:

```python
def test_primary_actions_use_explicit_verbs_instead_of_generic_confirm_copy() -> None:
    page = render_new_book_page(configured_provider)

    assert "生成开书方案" in page
    assert ">确定<" not in page
    assert ">提交<" not in page


def test_waiting_copy_explains_current_work_and_next_decision() -> None:
    page = render_chapter_review(book, chapters, running_chapter, canon)

    assert "当前阶段" in page or "正在进行的步骤" in page
    assert "完成后你要决定" in page
```

- [ ] **Step 2: Run the regression tests to verify they fail where copy is still generic**

Run:

```bash
pixi run pytest \
  tests/test_product_regressions.py::test_primary_actions_use_explicit_verbs_instead_of_generic_confirm_copy \
  tests/test_product_regressions.py::test_waiting_copy_explains_current_work_and_next_decision -v
```

Expected: at least one FAIL until the remaining generic button/copy text is normalized.

- [ ] **Step 3: Normalize the remaining copy and mobile/responsive spacing**

Do a final pass across `src/mynovel/ui_shell.py`, `src/mynovel/home_views.py`, `src/mynovel/product_views.py`, `src/mynovel/chapter_review_views.py`, and `src/mynovel/i18n.py` to ensure:

```python
# Good examples that should exist after the pass
"生成开书方案"
"进入当前任务"
"接受这版正文"
"继续自动修复"
"AI 已自动修复"
"待你确认"
```

And tighten responsive CSS so the new summary cards and status strip do not collapse badly on narrower widths:

```css
@media (max-width: 1100px) {
  .global-status-strip{grid-template-columns:minmax(0,1fr)}
  .result-slot-grid{grid-template-columns:minmax(0,1fr)}
  .review-summary-stack{grid-template-columns:minmax(0,1fr)}
}
```

- [ ] **Step 4: Run the high-signal UI regression suite**

Run:

```bash
pixi run pytest \
  tests/test_product_ui.py \
  tests/test_product_regressions.py \
  tests/test_chapter_review_ui.py \
  tests/test_dev_server.py -v
```

Expected: PASS across the UI-facing suite.

- [ ] **Step 5: Run the full project verification before claiming completion**

Run:

```bash
pixi run pytest -q
```

Expected: full suite PASS.

- [ ] **Step 6: Commit the final polish**

```bash
git add src/mynovel/ui_shell.py src/mynovel/home_views.py src/mynovel/product_views.py src/mynovel/chapter_review_views.py src/mynovel/i18n.py tests/test_product_ui.py tests/test_product_regressions.py tests/test_dev_server.py
git commit -m "feat: finish focused creative workbench uiux refresh"
```

---

## Self-Review

### Spec coverage

- Global visual language, tighter shell, and persistent status strip: Task 1
- Home as next-action dashboard and open-book single-task focus: Task 2
- Workspace and running chapter "AI doing work now" surfaces: Task 3
- Result-first review with state-change summary and AI self-fix summary: Task 4
- Copy consistency, waiting language, and final responsive polish: Task 5

No spec section is left without a corresponding task.

### Placeholder scan

- The plan contains no unresolved placeholder markers.
- Each code-changing step includes concrete code or markup examples.
- Each verification step includes an exact `pixi run pytest` command with expected outcomes.

### Type consistency

- Shared status-strip helper names are consistent across tasks: `render_global_status_strip`, `StatusStage`.
- New extraction modules are consistent across tasks: `open_book_views.py`, `workspace_views.py`, `ui_status_views.py`.
- Review summary helper names are consistent across tasks: `render_review_decision_summary`, `_render_completion_summary`, `_render_state_change_summary`, `_render_ai_fixed_summary`.
