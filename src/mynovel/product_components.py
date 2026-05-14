from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from mynovel.domain.models import (
    Book,
    Canon,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
    Chapter,
    ProviderConfig,
)
from mynovel.workflows.canon_proposal import (
    canon_proposal_completion_target,
    canon_proposal_readiness,
    section_locks_for_book,
)
from mynovel.word_targets import chapter_word_budget, format_word_count
from mynovel.i18n import DEFAULT_LOCALE, t


def render_model_setup_content(
    db_path: Path,
    provider_config: ProviderConfig | None,
    locale: str = DEFAULT_LOCALE,
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
    llm_ready = bool(llm_base_ready and llm_model_ready)
    key_ready = bool(config.llm_api_key)
    embedding_ready = bool(config.embedding_model.strip())
    rerank_ready = bool(config.rerank_model and config.rerank_model.strip())

    return f"""
      <aside class="setup-guide">
        {_setup_guide_card("1", "接口类型说明", "OpenAI-compatible 是唯一接口类型，兼容 OpenAI 接口协议的服务商均可使用。")}
        {_setup_guide_card("2", "完成后解锁开书", "所有必填项完成后，将解锁“开始创作第一本书”。")}
        {_setup_guide_card("3", "密钥本地保存", "访问密钥仅保存在本机，不会上传到任何服务器。")}
      </aside>
      <section class="model-config-panel">
        <div class="panel-head">
          <div>
            <h1>模型配置</h1>
            <h2>连接你的 AI 模型 <span class="info-dot">?</span></h2>
            <p>MyNovel 仅支持 OpenAI-compatible 接口，其他接口类型不支持。</p>
          </div>
        </div>
        <form method="post" action="/provider-config" class="model-config-form">
          <div class="model-field">
            <label>服务类型</label>
            <div class="select-shell"><span class="check-dot">✓</span><span>OpenAI-compatible</span><span>⌄</span></div>
            <p>目前仅支持 OpenAI-compatible 接口（包括 OpenAI 官方与兼容服务）</p>
          </div>
          {_input("llm_base_url", "接口地址", "https://api.example.com/v1", _field(config.llm_base_url), True, "✓" if llm_base_ready else "")}
          {_input("llm_api_key", "访问密钥", "", _field(config.llm_api_key), False, "✓" if key_ready else "", "password")}
          <div class="model-divider"></div>
          {_input("llm_model", "聊天模型", "gpt-4o-mini", _field(config.llm_model), True, "✓" if llm_model_ready else "")}
          {_input("embedding_model", "检索模型（可选）", "text-embedding-3-small", _field(config.embedding_model), True, "✓" if embedding_ready else "")}
          {_input("rerank_model", "重排模型（可选）", "bge-reranker-v2-m3", _field(config.rerank_model), False, "✓" if rerank_ready else "")}
          <details class="advanced-model-options">
            <summary class="button secondary">高级配置</summary>
            <section class="advanced-model-section">
              <h3>检索模型接口</h3>
              {_credential_checkbox("embedding_use_llm_credentials", "检索模型使用和对话模型一样的接口与密钥", config.embedding_use_llm_credentials)}
              {_input("embedding_base_url", "检索接口地址", "https://api.example.com/v1", _field(config.embedding_base_url))}
              {_input("embedding_api_key", "检索访问密钥", "", _field(config.embedding_api_key), False, "", "password")}
            </section>
            <section class="advanced-model-section">
              <h3>重排模型接口</h3>
              {_credential_checkbox("rerank_use_llm_credentials", "重排模型使用和对话模型一样的接口与密钥", config.rerank_use_llm_credentials)}
              {_input("rerank_base_url", "重排接口地址", "https://api.example.com/v1", _field(config.rerank_base_url))}
              {_input("rerank_api_key", "重排访问密钥", "", _field(config.rerank_api_key), False, "", "password")}
            </section>
          </details>
          <div class="model-actions">
            <button type="submit">保存配置</button>
          </div>
        </form>
      </section>
      <aside class="right-panel setup-aside">
        <section>
          <h2>准备创建书籍</h2>
          <p>完成以下设置后，即可开始创建你的第一本书。</p>
          <ol class="setup-checklist">
            {_check_item("选择 OpenAI-compatible 服务类型", "仅支持 OpenAI-compatible 接口", True)}
            {_check_item("配置接口地址", "访问正常", llm_ready)}
            {_check_item("保存访问密钥", "已安全保存在本机", key_ready)}
            {_check_item("选择聊天模型", config.llm_model or "待填写", bool(config.llm_model))}
            {_check_item("（可选）配置检索模型", "建议开启以后启用记忆与检索", embedding_ready, optional=True)}
            {_check_item("（可选）配置重排模型", "建议开启以提升检索质量", rerank_ready, optional=True)}
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


def render_canon_gate_main(canon: Canon | None, locked: bool = False) -> str:
    if canon is None:
        return "<p>还没有可信设定。</p>"
    content = canon.content
    summary_cards = [
        ("world", "世界规则", "12 条", "物理、魔法、社会等规则", "globe"),
        ("characters", "人物", "18 位", "主角、配角、NPC", "user"),
        ("factions", "势力", "7 个", "组织、阵营与派系", "flag"),
        ("locations", "地点", "24 处", "城市、区域、地标", "pin"),
        ("relationships", "关系", "56 条", "人物与势力关系网", "nodes"),
        ("foreshadowing", "伏笔账本", "28 条", "伏笔、线索与回收计划", "note"),
        ("chapter-summaries", "章节摘要", "10 章", "情节要点与阶段目标", "book"),
        ("state-history", "变化历史", "36 条", "提案过程变更记录", "clock"),
    ]
    warning = (
        (
            f'<div class="canon-warning">当前可信设定已锁定：版本 {canon.version} 是生产线事实源，'
            "只有通过审核的章节变化才能继续写入。</div>"
        )
        if locked
        else (
            '<div class="canon-warning">当前为草稿提案状态，只有锁定后，'
            "状态变化才会写入可信设定。</div>"
        )
    )
    detail_cards = [
        ("trusted_state.world_rules", content.get("world_rules", [])),
        ("trusted_state.characters", content.get("characters", [])),
        ("trusted_state.locations", content.get("locations", [])),
        ("trusted_state.relationships", content.get("relationships", [])),
        ("trusted_state.foreshadowing", content.get("foreshadowing", [])),
        ("trusted_state.chapter_summaries", content.get("chapter_summaries", [])),
        ("trusted_state.state_history", content.get("state_history", [])),
    ]
    return (
        warning
        + "<div class='canon-summary-grid'>"
        + "".join(
            f'<section id="{anchor}" class="canon-summary-card">'
            f"<span class='card-icon'>{_surface_icon(icon)}</span><h2>{label}</h2>"
            f"<strong>{count}</strong><p>{copy}</p><b aria-hidden='true'>›</b></section>"
            for anchor, label, count, copy, icon in summary_cards
        )
        + "</div>"
        + f"<section class='table-card chapter-production-basis'><h2>章节生产依据 · 前 10 章节奏</h2>{_render_chapter_rhythm(content)}</section>"
        + "<div class='state-sections detail-state-sections'>"
        + "".join(
            f"<section class='data-card'><h2>{_state_label(key)}</h2>{_render_value(value)}</section>"
            for key, value in detail_cards
        )
        + "</div>"
    )


def render_canon_gate_aside(
    book: Book,
    canon: Canon | None,
    chapters: list[Chapter],
    locked: bool = False,
    proposal_revision: CanonProposalRevision | None = None,
) -> str:
    book_id = book.id or 0
    content = canon.content if canon is not None else {}
    readiness = canon_proposal_readiness(content)
    completion_target = canon_proposal_completion_target(content, section_locks_for_book(book))
    ready_to_lock = locked or readiness.complete
    active_revision = (
        proposal_revision
        if proposal_revision is not None
        and proposal_revision.status
        in {
            CanonProposalRevisionStatus.RUNNING,
            CanonProposalRevisionStatus.PENDING,
            CanonProposalRevisionStatus.FAILED,
        }
        else None
    )
    risk_items = _audit_risk_items(chapters)
    counts = {"high": 0, "medium": 0, "low": 0, "tip": 0}
    for item in risk_items:
        counts[item["level_key"]] += 1
    risk_rows = (
        "".join(
            _risk_item(item["level"], item["title"], item["copy"], item["href"])
            for item in risk_items[:6]
        )
        if risk_items
        else "<p>暂无未处理审计风险。</p>"
    )
    if locked:
        gate_title = "章节生产已解锁"
        status = "已完成定盘"
        gate_copy = "这本书已经完成开书定盘，可以继续进入章节生产和审核。"
        actions = f"""
          <a class="button secondary" href="/book/{book_id}">返回项目</a>
          <a class="button" href="/review">进入审核</a>
"""
        confirmation = """
        <section class="lock-confirmation">
          <h2>后续如何修改</h2>
          <p>后续章节通过审核后，新的变化会继续写入可信设定。</p>
        </section>
"""
    elif active_revision is not None:
        gate_title, status, gate_copy, confirmation, actions = _render_revision_gate_state(
            book_id,
            active_revision,
        )
    elif not ready_to_lock:
        gate_title = "还不能进入下一步"
        status = "待补全"
        status = "需要补全定盘"
        gate_copy = "还缺少必要设定。请先让 AI 补全定盘，确认预览后再继续。"
        repair_action = (
            f'<a class="button" href="/book/{book_id}/state#canon-completion">让 AI 补全定盘</a>'
            if completion_target is not None
            else ""
        )
        actions = f"{repair_action}{_render_abandon_settings_action(book_id)}"
        confirmation = """
        <section class="lock-confirmation">
          <h2>需要先补齐什么</h2>
          <p>人物、势力、地点、关系、伏笔和章节节奏足够明确后，才能进入章节生产。</p>
        </section>
"""
    else:
        gate_title = "下一步：开始章节生产"
        status = "可以进入章节生产"
        gate_copy = "开书定盘已达到最低要求。点击下一步会固定当前设定，并进入章节生产步骤。"
        actions = f"""
          <form method="post" action="/lock-canon" class="compact-form">
            <input type="hidden" name="book_id" value="{book_id}">
            <button type="submit">下一步</button>
          </form>
          {_render_abandon_settings_action(book_id)}
"""
        confirmation = """
        <section class="lock-confirmation">
          <h2>点击下一步后</h2>
          <p>当前设定会成为后续章节的写作依据；之后仍可通过章节审核继续补充新的变化。</p>
        </section>
"""
    return f"""
      <aside class="right-panel audit-risk-panel">
        <section class="force-gate">
          <h2>{gate_title}</h2>
          <p>{gate_copy}</p>
          <p>当前进度：<strong>{status}</strong></p>
        </section>
        {confirmation}
        <div class="gate-actions">{actions}</div>
        <section>
          <h2>审计风险 <span class="muted">(AI + 规则检测)</span></h2>
          <div class="risk-summary">
            <span class="risk high">高 {counts["high"]}</span>
            <span class="risk medium">中 {counts["medium"]}</span>
            <span class="risk low">低 {counts["low"]}</span>
            <span>提示 {counts["tip"]}</span>
          </div>
          <div class="risk-list">{risk_rows}</div>
        </section>
      </aside>
"""


def _render_abandon_settings_action(book_id: int) -> str:
    return f"""
          <form method="post" action="/abandon-book" class="compact-form">
            <input type="hidden" name="book_id" value="{book_id}">
            <button class="secondary danger" type="submit">放弃设定，重开一本</button>
          </form>
"""


def _render_revision_gate_state(
    book_id: int,
    revision: CanonProposalRevision,
) -> tuple[str, str, str, str, str]:
    if revision.status == CanonProposalRevisionStatus.RUNNING:
        gate_title = "等待 AI 生成预览"
        status = "AI 生成中"
        gate_copy = "AI 正在生成可审核预览，完成后在左侧确认是否应用。"
        confirmation = """
        <section class="lock-confirmation">
          <h2>正在生成预览</h2>
          <p>生成完成前不会写入可信设定；保持当前页面，系统会自动刷新。</p>
        </section>
"""
        actions = """
          <a class="button" href="#canon-revision-job">查看生成进度</a>
          <button type="button" disabled>生成完成后再确认</button>
"""
    elif revision.status == CanonProposalRevisionStatus.FAILED:
        gate_title = "AI 预览生成失败"
        status = "生成失败"
        gate_copy = "这次 AI 修订没有生成可用预览，可以在左侧重新生成或调整意见。"
        confirmation = """
        <section class="lock-confirmation">
          <h2>需要重新生成</h2>
          <p>先查看失败原因，再缩小修改范围或重新提交给 AI。</p>
        </section>
"""
        actions = f"""
          <a class="button" href="#canon-revision-job">查看失败原因</a>
          <a class="button secondary" href="/book/{book_id}/state">查看全部分区</a>
"""
    else:
        gate_title = "先确认 AI 修订预览"
        status = "预览待确认"
        gate_copy = "先审核左侧 AI 修订预览；应用后再判断是否可锁定。"
        confirmation = """
        <section class="lock-confirmation">
          <h2>先审核预览</h2>
          <p>当前预览尚未写入定盘提案；应用后才会更新人物、势力、地点等分区。</p>
        </section>
"""
        actions = """
          <a class="button" href="#canon-revision-job">查看修订预览</a>
          <button type="button" disabled>确认后再锁定</button>
"""
    return gate_title, status, gate_copy, confirmation, actions


def render_chapter_production_main(
    chapter: Chapter,
    locale: str = DEFAULT_LOCALE,
) -> str:
    target_words = chapter_word_budget(chapter)
    current_text = _current_chapter_candidate(chapter)
    current_words = chapter.word_count or len(current_text)
    mode_title, status_copy = _chapter_running_mode(chapter, locale)
    return f"""
      <section class="reader-panel production-main chapter-task-board">
        <div class="chapter-toolbar">
          <div>
            <p class="muted">{html.escape(status_copy)}</p>
            <h1>{t("chapter.number", locale, number=chapter.number)} {html.escape(chapter.title)}</h1>
          </div>
          <div class="toolbar-metrics">
            <span>{t("running_board.word_stats", locale, current=current_words, target=format_word_count(target_words))}</span>
            <span class="status-pill pending">{t("running_board.auto_refreshing", locale)}</span>
          </div>
        </div>
        <section class="run-status-strip">
          <div>
            <strong>{html.escape(mode_title)}</strong>
            <span>{t("running_board.refresh_copy", locale)}</span>
            {_running_note_line(chapter, locale)}
          </div>
          <a class="button secondary" href="/chapter/{chapter.id or 0}">{t("running_board.refresh_now", locale)}</a>
        </section>
        <section class="chapter-stage-chain" aria-label="{html.escape(t('running_board.stage_chain', locale), quote=True)}">
          {_render_stage_chain(chapter, locale)}
        </section>
        <section class="chapter-result-grid">
          {_render_result_slot("plan", t("running_board.slot_plan", locale), chapter.plan, locale)}
          {_render_result_slot("context", t("running_board.slot_context", locale), chapter.context_package, locale)}
          {_render_result_slot("draft", t("running_board.slot_draft", locale), current_text, locale)}
          {_render_result_slot("delta", t("running_board.slot_delta", locale), chapter.state_delta.get("changes", []), locale, completed=_delta_stage_completed(chapter))}
          {_render_result_slot("audit", t("running_board.slot_audit", locale), chapter.audit_report.get("issues", []), locale, completed=_audit_stage_completed(chapter))}
        </section>
        <script>setTimeout(() => window.location.reload(), 3000)</script>
      </section>
"""


def render_chapter_production_aside(
    chapter: Chapter,
    locale: str = DEFAULT_LOCALE,
) -> str:
    mode_title, status_copy = _chapter_running_mode(chapter, locale)
    current_stage = _running_stage_key(chapter)
    target_words = chapter_word_budget(chapter)
    current_text = _current_chapter_candidate(chapter)
    current_words = chapter.word_count or len(current_text)
    return f"""
      <aside class="right-panel production-aside">
        <section class="current-run">
          <h2>{html.escape(mode_title)}</h2>
          <p><span class="status-dot warn"></span>{html.escape(status_copy)}</p>
          {_render_running_request(chapter, locale)}
        </section>
        <section class="current-run">
          <h2>{t("running_board.side_status", locale)}</h2>
          <dl class="revision-metrics">
            <dt>{t("running_board.side_current_stage", locale)}</dt><dd>{html.escape(_stage_title(current_stage, locale))}</dd>
            <dt>{t("running_board.side_word_progress", locale)}</dt><dd>{current_words} / {html.escape(format_word_count(target_words))}</dd>
            <dt>{t("running_board.side_next_decision", locale)}</dt><dd>{t("running_board.side_next_decision_copy", locale)}</dd>
          </dl>
        </section>
        <a class="button secondary" href="/chapter/{chapter.id or 0}">{t("running_board.refresh_now", locale)}</a>
      </aside>
"""


def _chapter_running_mode(chapter: Chapter, locale: str = DEFAULT_LOCALE) -> tuple[str, str]:
    note = str(chapter.reviewer_note or "")
    if note.startswith("AI 修复中"):
        return t("running_board.mode_repair", locale), t("running_board.mode_repair_status", locale)
    return t("running_board.mode_generate", locale), t("running_board.mode_generate_status", locale)


def _current_chapter_candidate(chapter: Chapter) -> str:
    return chapter.revised_text or chapter.draft_text or chapter.final_text or ""


def _render_stage_chain(chapter: Chapter, locale: str) -> str:
    current_key = _running_stage_key(chapter)
    stage_keys = ("plan", "context", "draft", "delta", "audit")
    items = []
    for index, key in enumerate(stage_keys, start=1):
        if index > 1:
            items.append('<span class="chapter-stage-link" aria-hidden="true"></span>')
        state = _stage_state(chapter, key, current_key)
        items.append(
            f'<article class="chapter-stage {state}" data-stage="{html.escape(key, quote=True)}">'
            f"<span>{index}</span>"
            f"<strong>{html.escape(_stage_title(key, locale))}</strong>"
            f"<em>{html.escape(_stage_status_label(state, locale))}</em>"
            f"<p>{html.escape(_stage_copy(key, state, locale))}</p>"
            "</article>"
        )
    return "".join(items)


def _running_stage_key(chapter: Chapter) -> str:
    if not chapter.plan:
        return "plan"
    if not chapter.context_package:
        return "context"
    if not _current_chapter_candidate(chapter):
        return "draft"
    if not _delta_stage_completed(chapter):
        return "delta"
    if not _audit_stage_completed(chapter):
        return "audit"
    return "audit"


def _stage_state(chapter: Chapter, key: str, current_key: str) -> str:
    if key == "plan" and chapter.plan:
        return "done"
    if key == "context" and chapter.context_package:
        return "done"
    if key == "draft" and _current_chapter_candidate(chapter):
        return "done"
    if key == "delta" and _delta_stage_completed(chapter):
        return "done"
    if key == "audit" and _audit_stage_completed(chapter):
        return "done"
    if key == current_key:
        return "current"
    return "pending"


def _stage_title(key: str, locale: str) -> str:
    return {
        "plan": t("pipeline.plan", locale),
        "context": t("pipeline.context", locale),
        "draft": t("pipeline.draft_cn", locale),
        "delta": t("pipeline.extract", locale),
        "audit": t("pipeline.audit", locale),
    }[key]


def _stage_status_label(state: str, locale: str) -> str:
    return {
        "done": t("running_board.stage_done", locale),
        "current": t("running_board.stage_current", locale),
        "pending": t("running_board.stage_pending", locale),
    }[state]


def _stage_copy(key: str, state: str, locale: str) -> str:
    if state == "done":
        return _slot_ready_copy(key, locale)
    if state == "current":
        return _slot_waiting_copy(key, locale)
    return t("running_board.stage_pending_copy", locale)


def _render_result_slot(
    slot: str,
    title: str,
    value: Any,
    locale: str,
    *,
    completed: bool | None = None,
) -> str:
    slot_completed = _slot_completed(slot, value) if completed is None else completed
    preview = _render_result_slot_preview(slot, value, slot_completed, locale)
    status = _slot_ready_copy(slot, locale) if slot_completed else _slot_waiting_copy(slot, locale)
    state = "ready" if slot_completed else "pending"
    return f"""
      <article class="chapter-result-slot {state}" data-slot="{html.escape(slot, quote=True)}">
        <header>
          <strong>{html.escape(title)}</strong>
          <span>{html.escape(status)}</span>
        </header>
        <div class="chapter-slot-preview">{preview}</div>
      </article>
"""


def _slot_completed(slot: str, value: Any) -> bool:
    if slot in {"plan", "context"}:
        return isinstance(value, dict) and bool(value)
    if slot == "draft":
        return bool(str(value or "").strip())
    return bool(value)


def _render_result_slot_preview(slot: str, value: Any, completed: bool, locale: str) -> str:
    if not completed:
        return f"<p>{html.escape(t('running_board.result_pending', locale))}</p>"
    if slot in {"delta", "audit"} and isinstance(value, list) and not value:
        return f"<p>{html.escape(_empty_result_copy(slot, locale))}</p>"
    if slot == "draft" and not str(value or "").strip():
        return f"<p>{html.escape(t('running_board.none_output', locale))}</p>"
    if slot == "draft":
        text = html.escape(str(value)[:180])
        if len(str(value)) > 180:
            text += "..."
        return f"<p>{text}</p>"
    return _render_value(value)


def _delta_stage_completed(chapter: Chapter) -> bool:
    return "changes" in chapter.state_delta or bool(chapter.audit_report)


def _audit_stage_completed(chapter: Chapter) -> bool:
    return "issues" in chapter.audit_report


def _empty_result_copy(slot: str, locale: str) -> str:
    return {
        "delta": t("running_board.none_delta", locale),
        "audit": t("running_board.none_audit", locale),
    }.get(slot, t("running_board.none_output", locale))


def _slot_ready_copy(key: str, locale: str) -> str:
    return {
        "plan": t("running_board.plan_ready", locale),
        "context": t("running_board.context_ready", locale),
        "draft": t("running_board.draft_ready", locale),
        "delta": t("running_board.delta_ready", locale),
        "audit": t("running_board.audit_ready", locale),
    }[key]


def _slot_waiting_copy(key: str, locale: str) -> str:
    return {
        "plan": t("running_board.plan_waiting", locale),
        "context": t("running_board.context_waiting", locale),
        "draft": t("running_board.draft_waiting", locale),
        "delta": t("running_board.delta_waiting", locale),
        "audit": t("running_board.audit_waiting", locale),
    }[key]


def _render_running_request(chapter: Chapter, locale: str = DEFAULT_LOCALE) -> str:
    note = _running_repair_note(chapter, locale)
    if note:
        return f"""
          <p class="review-panel-copy">{t("running_board.request_note", locale, note=html.escape(note))}</p>
          <dl class="revision-metrics">
            <dt>{t("running_board.request_task_type", locale)}</dt><dd>{t("running_board.request_task_repair", locale)}</dd>
            <dt>{t("running_board.request_note_label", locale)}</dt><dd>{html.escape(note)}</dd>
          </dl>
"""
    return f"""
      <p class="muted">{t("running_board.request_running", locale)}</p>
"""


def _running_repair_note(chapter: Chapter, locale: str = DEFAULT_LOCALE) -> str:
    note = str(chapter.reviewer_note or "").strip()
    for prefix in ("AI 修复中：", "AI 修复中:"):
        if note.startswith(prefix):
            return note.removeprefix(prefix).strip()
    if note == "AI 修复中。":
        return t("running_board.repair_note_fallback", locale)
    return ""


def _running_note_line(chapter: Chapter, locale: str = DEFAULT_LOCALE) -> str:
    note = _running_repair_note(chapter, locale)
    if not note:
        return ""
    return f"<span>{t('running_board.request_note', locale, note=html.escape(note))}</span>"


def render_review_tabs() -> str:
    return """
      <nav class="review-tabs" aria-label="章节审核">
        <span class="active">审计问题</span>
        <span>状态变化待验证</span>
        <span>AI 修订摘要</span>
        <span>影响范围</span>
      </nav>
"""


def render_impact_scope(chapter: Chapter) -> str:
    changes = [
        change for change in chapter.state_delta.get("changes", []) if isinstance(change, dict)
    ]
    buckets: dict[str, list[str]] = {}
    for change in changes:
        bucket = str(change.get("type") or "变化")
        buckets.setdefault(bucket, []).append(
            str(change.get("target") or change.get("change") or "待确认")
        )
    if not buckets:
        buckets = {"人物": ["待确认"], "地点": ["待确认"], "伏笔": ["待确认"]}
    cards = "".join(
        f"<section><strong>{html.escape(key)} ({len(values)})</strong><p>{html.escape('、'.join(values[:3]))}</p></section>"
        for key, values in buckets.items()
    )
    return f"<section class='impact-scope'><h2>影响范围</h2><div>{cards}</div></section>"


def render_accepted_result(chapter: Chapter) -> str:
    return f"""
      <section class="accepted-result">
        <h2>可信设定更新结果 <span class="status-pill trusted">已写入</span></h2>
        <div class="stack-list">
          <p>人物状态 <span>已更新</span></p>
          <p>地点 <span>已更新</span></p>
          <p>伏笔账本 <span>已更新</span></p>
          <p>章节摘要索引 <span>已更新</span></p>
          <p>运行记录完成 <span>已归档</span></p>
        </div>
        <section class="data-card"><h2>恢复点</h2><p>第 {chapter.number:02d} 章已写入可信设定，可安全恢复到此状态。</p></section>
      </section>
"""


def render_completed_progress(
    book: Book,
    chapters: list[Chapter],
    canon: Canon | None,
) -> str:
    total_words = sum(chapter.word_count for chapter in chapters[:10])
    canon_version = canon.version if canon else 0
    rows = "".join(
        f"<tr><td>{chapter.number:02d}</td><td>{html.escape(chapter.title)}</td>"
        f"<td>{html.escape(chapter.summary or '已完成本章生产。')}</td>"
        f"<td>{chapter.word_count:,}</td><td>已批准</td><td>v{index}</td></tr>"
        for index, chapter in enumerate(chapters[:10], start=1)
    )
    return f"""
      <section class="main-panel project-progress-overview">
        <div class="panel-head">
          <div><h1>项目进度总览</h1><p>已完成多章生产、审核、修订、人工批准和可信设定写入。</p></div>
          <a class="button secondary" href="/book/{book.id}/quality">查看全局审计报告</a>
        </div>
        <div class="metric-grid progress-metrics">
          <div><span>已批准章节</span><strong>{len(chapters[:10])}</strong><em>全部已通过人工关卡</em></div>
          <div><span>待审核章节</span><strong>0</strong><em>无需处理</em></div>
          <div><span>累计字数</span><strong>{total_words:,}</strong><em>字 / 约 {round(total_words / 3000, 1)} 万</em></div>
          <div><span>可信设定版本</span><strong>v{canon_version}</strong><em>已连续更新</em></div>
        </div>
        <section class="table-card"><h2>已批准章节索引</h2><table><tbody>{rows}</tbody></table></section>
        <div class="completion-grid">
          <section class="data-card"><h2>质量复盘</h2><p>风险趋势、节奏曲线和字数曲线已生成。</p></section>
          <section class="data-card"><h2>最近批准章节</h2><p>第 10 章已写入可信设定，可继续阅读或进入下一章。</p></section>
        </div>
      </section>
"""


def render_completed_aside(book: Book, canon: Canon | None) -> str:
    version = canon.version if canon else 0
    return f"""
      <aside class="right-panel completion-aside">
        <section class="canon-update-overview">
          <h2>可信设定更新总览 <span class="status-pill trusted">已连续更新到 v{version}</span></h2>
          <div class="stack-list">
            <p>人物状态 <span>已更新 ›</span></p><p>地点 <span>已更新 ›</span></p>
            <p>伏笔账本 <span>已更新 ›</span></p><p>关系 <span>已更新 ›</span></p>
            <p>章节摘要 <span>已更新 ›</span></p><p>运行记录 <span>已更新 ›</span></p>
          </div>
        </section>
        <section><h2>恢复点</h2><p>当前可恢复到：第 10 章（已写入可信设定）。</p></section>
        <a class="button" href="/book/{book.id}">继续生产第 11 章</a>
        <a class="button secondary" href="/book/{book.id}/export.md">导出已批准章节</a>
        <a class="button secondary" href="/book/{book.id}/state">查看可信设定历史</a>
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


def _field(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def _check_item(title: str, subtitle: str, done: bool, optional: bool = False) -> str:
    state = "done" if done else "optional" if optional else "todo"
    icon = "✓" if done else "○"
    return (
        f'<li class="{state}"><span>{icon}</span><div><strong>{html.escape(title)}</strong>'
        f"<p>{html.escape(subtitle)}</p></div></li>"
    )


def _render_chapter_rhythm(content: dict[str, Any]) -> str:
    chapters = content.get("chapter_summaries") or content.get("chapter_directions") or []
    if not isinstance(chapters, list) or not chapters:
        chapters = [
            {"chapter": index, "title": f"第 {index:02d} 章", "summary": "阶段性推进与新目标"}
            for index in range(1, 11)
        ]
    rows = []
    for index, chapter in enumerate(chapters[:10], start=1):
        if isinstance(chapter, dict):
            title = chapter.get("title") or chapter.get("chapter") or f"第 {index:02d} 章"
            goal = (
                chapter.get("summary")
                or chapter.get("direction")
                or chapter.get("goal")
                or "推进承诺"
            )
        else:
            title = f"第 {index:02d} 章"
            goal = str(chapter)
        rows.append(
            f"<tr><td>{index:02d}</td><td>{html.escape(str(title))}</td><td>{html.escape(str(goal))}</td></tr>"
        )
    return "<table><tbody>" + "".join(rows) + "</tbody></table>"


def _audit_risk_items(chapters: list[Chapter]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for chapter in chapters:
        report = chapter.audit_report or {}
        issues = report.get("issues", [])
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, dict) or issue.get("resolved"):
                continue
            level, level_key = _risk_level(issue.get("severity") or report.get("risk_level"))
            title = str(issue.get("title") or issue.get("type") or "未命名审计风险").strip()
            detail = str(
                issue.get("detail")
                or issue.get("description")
                or issue.get("message")
                or issue.get("suggested_fix")
                or "需要人工确认。"
            ).strip()
            source = f"第 {chapter.number:02d} 章《{chapter.title}》"
            items.append(
                {
                    "level": level,
                    "level_key": level_key,
                    "title": title,
                    "copy": f"{source}：{detail}",
                    "href": f"/chapter/{chapter.id or 0}",
                }
            )
    order = {"high": 0, "medium": 1, "low": 2, "tip": 3}
    return sorted(items, key=lambda item: order[item["level_key"]])


def _risk_level(value: object) -> tuple[str, str]:
    normalized = str(value or "").lower()
    if normalized in {"high", "高"}:
        return "高", "high"
    if normalized in {"medium", "mid", "中"}:
        return "中", "medium"
    if normalized in {"low", "低"}:
        return "低", "low"
    return "提示", "tip"


def _risk_item(level: str, title: str, copy: str, href: str = "#") -> str:
    level_class = {"高": "high", "中": "medium", "低": "low"}.get(level, "low")
    return (
        f'<article><span class="risk-badge {level_class}">{html.escape(level)}</span>'
        f"<div><strong>{html.escape(title)}</strong><p>{html.escape(copy)}</p></div>"
        f'<a class="button secondary" href="{html.escape(href, quote=True)}">查看</a></article>'
    )


def _render_value(value: Any) -> str:
    if isinstance(value, list):
        visible_items = [item for item in value if not _is_low_information_state_item(item)]
        if not visible_items:
            return "<p>—</p>"
        return (
            "<ul>"
            + "".join(f"<li>{_render_nested(item)}</li>" for item in visible_items[:6])
            + "</ul>"
        )
    if isinstance(value, dict):
        return (
            "<dl>"
            + "".join(
                f"<dt>{_label_key(key)}</dt><dd>{_render_nested(item)}</dd>"
                for key, item in value.items()
            )
            + "</dl>"
        )
    if value in (None, ""):
        return "<p>—</p>"
    return f"<p>{html.escape(str(value))}</p>"


def _render_nested(value: Any) -> str:
    if isinstance(value, dict):
        concise = _unknown_target_detail(value)
        if concise:
            return _short_text(concise)
        return "；".join(
            f"{_label_key(k)}：{_short_text(v)}"
            for k, v in value.items()
            if not _is_internal_state_key(k)
        )
    if isinstance(value, list):
        return "、".join(_short_text(item) for item in value)
    return _short_text(value)


def _is_internal_state_key(key: object) -> bool:
    return str(key) in {"chapter_title", "updated_at", "accepted_at"}


def _unknown_target_detail(value: dict) -> str:
    if str(value.get("name") or value.get("target") or "").strip() != "待确认":
        return ""
    return str(value.get("detail") or value.get("change") or "").strip()


def _is_low_information_state_item(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if str(value.get("name") or value.get("target") or "").strip() != "待确认":
        return False
    detail = str(value.get("detail") or value.get("change") or "").strip()
    low_information_values = {
        "人物",
        "关系",
        "地点",
        "资源",
        "伏笔",
        "信息暴露",
        "characters",
        "relationships",
        "locations",
        "resources",
        "foreshadowing",
        "information_exposure",
        "foreshadowing_and_info",
        "foreshadowing_and_information",
    }
    return detail in low_information_values


def _label_key(key: object) -> str:
    labels = {
        "chapter": "章节",
        "changes": "变化",
        "detail": "内容",
        "direction": "方向",
        "from": "起点",
        "goal": "目标",
        "identity": "身份",
        "impact": "影响",
        "mechanism": "机制",
        "motivation": "动机",
        "name": "名称",
        "personality": "性格",
        "role": "定位",
        "rules": "规则",
        "setting": "背景",
        "summary": "摘要",
        "target": "对象",
        "title": "标题",
        "to": "终点",
        "trait": "特质",
        "type": "类型",
    }
    return html.escape(labels.get(str(key), str(key)))


def _state_label(key: str) -> str:
    labels = {
        "trusted_state.characters": "人物",
        "trusted_state.chapter_summaries": "章节摘要",
        "trusted_state.foreshadowing": "伏笔账本",
        "trusted_state.locations": "地点",
        "trusted_state.relationships": "关系",
        "trusted_state.state_history": "变化历史",
        "trusted_state.world_rules": "世界规则",
    }
    return labels.get(key, key)


def _short_text(value: object, limit: int = 80) -> str:
    text = str(value)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return html.escape(text)


def _stage_card(number: int, title: str, status: str, copy: str, state: str) -> str:
    return (
        f'<article class="stage-card {state}"><span>{number}</span><h3>{html.escape(title)}</h3>'
        f"<strong>{html.escape(status)}</strong><p>{html.escape(copy)}</p></article>"
    )


def _render_context_package(context: dict[str, Any]) -> str:
    if not context:
        return "<p class='muted'>上下文包尚未写入，任务完成后会显示可信设定与章节计划。</p>"
    return _render_value(context)


def _render_draft_progress(chapter: Chapter) -> str:
    text = _current_chapter_candidate(chapter)
    target_words = chapter_word_budget(chapter)
    current_words = chapter.word_count or len(text)
    progress = round(current_words / target_words * 100) if target_words else 0
    snippet = html.escape(text[:160]) + ("..." if len(text) > 160 else "")
    if not snippet:
        snippet = "正文尚未生成，完成后会在这里显示候选文本。"
    return f"""
      <dl><dt>目标字数</dt><dd>{html.escape(format_word_count(target_words))}左右</dd><dt>当前字数</dt><dd>{current_words} 字（{progress}%）</dd></dl>
      <p class="draft-snippet">{snippet}</p>
"""


def _render_state_delta_preview(chapter: Chapter) -> str:
    changes = chapter.state_delta.get("changes", [])
    if not changes:
        return "<p class='muted'>状态变化尚未提取，任务完成后需要人工确认。</p>"
    if isinstance(changes, list):
        return (
            "<ul>" + "".join(f"<li>{_render_nested(item)}</li>" for item in changes[:6]) + "</ul>"
        )
    return _render_value(changes)


def _gate_item(title: str, copy: str, level: str) -> str:
    return (
        f"<article><span class='gate-icon'>{html.escape(level)}</span>"
        f"<div><strong>{html.escape(title)}</strong><p>{html.escape(copy)}</p></div></article>"
    )


def _surface_icon(name: str) -> str:
    icons = {
        "book": "▤",
        "clock": "◷",
        "flag": "⚑",
        "globe": "◎",
        "nodes": "⌘",
        "note": "▣",
        "pin": "⌖",
        "user": "♙",
    }
    return html.escape(icons.get(name, "◇"))
