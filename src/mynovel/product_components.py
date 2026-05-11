from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from mynovel.domain.models import Canon, Chapter, ProviderConfig
from mynovel.i18n import DEFAULT_LOCALE


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
    llm_ready = bool(config.llm_base_url.strip() and config.llm_model.strip())
    key_ready = bool(config.llm_api_key)
    embedding_ready = bool(config.embedding_model.strip())
    rerank_ready = bool(config.rerank_model and config.rerank_model.strip())

    return f"""
      <aside class="project-context setup-project">
        <div class="project-identity">
          <div class="project-cover forest-cover" aria-hidden="true"></div>
          <div>
            <h2>未命名项目</h2>
            <p>尚未创建书籍</p>
            <a class="button secondary project-overview" href="/">项目概览</a>
          </div>
        </div>
      </aside>
      <section class="main-panel model-config-panel">
        <div class="panel-head">
          <div>
            <h1>模型配置</h1>
            <h2>连接你的 AI 模型 <span class="info-dot">i</span></h2>
            <p>MyNovel 仅支持 OpenAI-compatible 接口，其他接口类型不支持。</p>
          </div>
        </div>
        <form method="post" action="/provider-config" class="model-config-form">
          <div class="model-field">
            <label>服务类型</label>
            <div class="select-shell"><span class="check-dot">✓</span><span>OpenAI-compatible</span><span>⌄</span></div>
            <p>目前仅支持 OpenAI-compatible 接口（包括 OpenAI 官方与兼容服务）</p>
          </div>
          {_input("llm_base_url", "接口地址", "https://api.example.com/v1", _field(config.llm_base_url), True, "✓")}
          {_input("llm_api_key", "API Key", "", _field(config.llm_api_key), False, "✓", "password")}
          <div class="model-divider"></div>
          {_input("llm_model", "聊天模型", "gpt-4o-mini", _field(config.llm_model), True, "✓")}
          {_input("embedding_model", "Embedding（可选）", "text-embedding-3-small", _field(config.embedding_model), True, "✓")}
          <input type="hidden" name="embedding_use_llm_credentials" value="{"1" if config.embedding_use_llm_credentials else "0"}">
          <input type="hidden" name="embedding_base_url" value="{_field(config.embedding_base_url)}">
          <input type="hidden" name="embedding_api_key" value="{_field(config.embedding_api_key)}">
          {_input("rerank_model", "Rerank（可选）", "bge-reranker-v2-m3", _field(config.rerank_model), False, "✓" if rerank_ready else "")}
          <input type="hidden" name="rerank_use_llm_credentials" value="{"1" if config.rerank_use_llm_credentials else "0"}">
          <input type="hidden" name="rerank_base_url" value="{_field(config.rerank_base_url)}">
          <input type="hidden" name="rerank_api_key" value="{_field(config.rerank_api_key)}">
          <div class="model-actions">
            <button class="secondary" type="submit">测试连接</button>
            <button type="submit">保存配置</button>
            <a class="button secondary" href="/provider-config">高级选项 ›</a>
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
            {_check_item("保存 API Key", "已安全保存在本机", key_ready)}
            {_check_item("选择聊天模型", config.llm_model or "待填写", bool(config.llm_model))}
            {_check_item("（可选）配置 Embedding", "建议开启以后启用记忆与检索", embedding_ready, optional=True)}
            {_check_item("（可选）配置 Rerank", "建议开启以提升检索质量", rerank_ready, optional=True)}
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


def render_canon_gate_main(canon: Canon | None) -> str:
    if canon is None:
        return "<p>还没有可信设定。</p>"
    content = canon.content
    cards = [
        ("世界规则", content.get("world_rules", [])),
        ("人物", content.get("characters", [])),
        ("势力", content.get("factions", []) or content.get("organizations", [])),
        ("地点", content.get("locations", [])),
        ("关系", content.get("relationships", [])),
        ("伏笔账本", content.get("foreshadowing", [])),
        ("章节摘要", content.get("chapter_summaries", [])),
        ("变化历史", content.get("state_history", [])),
    ]
    return (
        '<div class="canon-warning">当前为可信设定提案（未锁定）：该内容为 AI 生成的初始设定，仅供参考。'
        "只有在你确认并锁定后，才会成为可信事实源。</div>"
        "<div class='state-sections canon-state-grid'>"
        + "".join(
            f"<section class='data-card'><h2>{label}</h2>{_render_value(value)}</section>"
            for label, value in cards
        )
        + "</div>"
        f"<section class='table-card rhythm-board'><h2>前 10 章节奏</h2>{_render_chapter_rhythm(content)}</section>"
    )


def render_canon_gate_aside(book_id: int, canon: Canon | None) -> str:
    _ = canon
    return f"""
      <aside class="right-panel audit-risk-panel">
        <section>
          <h2>审计风险 <span class="muted">(AI + 规则检测)</span></h2>
          <div class="risk-summary">
            <span class="risk high">高 3</span>
            <span class="risk medium">中 2</span>
            <span class="risk low">低 2</span>
            <span>提示 3</span>
          </div>
          <div class="risk-list">
            {_risk_item("高", "世界规则边界模糊", "时间法则与生死规则在部分情境下可能冲突。")}
            {_risk_item("高", "势力动机不清", "灰烬教团的核心目标与手段尚未明确。")}
            {_risk_item("中", "角色动机跳跃", "主角加入队伍的动机过弱，缺少关键触发。")}
            {_risk_item("低", "地点名称一致性提示", "黑石峡谷曾出现多种写法。")}
          </div>
        </section>
        <section class="force-gate">
          <h2>强制 Gate</h2>
          <p>必须由作者确认并锁定可信设定，生产线才能解锁。</p>
          <p>当前状态：<strong>尚未锁定</strong></p>
        </section>
        <div class="gate-actions">
          <a class="button secondary" href="/book/{book_id}">返回修改</a>
          <a class="button secondary" href="/book/{book_id}/state">让 AI 修复</a>
          <a class="button" href="/book/{book_id}">锁定可信设定并开始生产</a>
        </div>
      </aside>
"""


def render_chapter_production_main(chapter: Chapter) -> str:
    return f"""
      <section class="reader-panel production-main">
        <div class="chapter-toolbar">
          <div>
            <p class="muted">当前阶段：生成草稿（AI 正在撰写中）</p>
            <h1>第 {chapter.number:02d} 章 {html.escape(chapter.title)}</h1>
          </div>
          <div class="toolbar-metrics"><span>字数统计：{chapter.word_count or 1248} / 预计 2,800</span><button class="secondary" type="button">显示设置⌄</button></div>
        </div>
        <div class="production-stage-grid">
          {_stage_card(1, "规划本章", "已完成", "目标与情节骨架确认", "done")}
          {_stage_card(2, "编译上下文", "已完成", "收集可信设定与前文信息", "done")}
          {_stage_card(3, "生成草稿", "进行中 68%", "AI 正在撰写章节内容", "current")}
          {_stage_card(4, "提取状态变化", "等待中", "识别人物与世界变化", "pending")}
          {_stage_card(5, "AI 审计", "等待中", "检测风险与一致性问题", "pending")}
          {_stage_card(6, "AI 修订", "等待中", "按建议优化章节内容", "pending")}
          {_stage_card(7, "等待人工审核", "等待中", "作者审核写入可信设定", "pending")}
        </div>
        <div class="production-grid">
          <section class="data-card"><h2>上下文包 <span class="muted">（已编译完成）</span></h2>{_render_context_package(chapter.context_package)}</section>
          <section class="data-card draft-preview"><h2>生成草稿 <span class="muted">（AI 撰写中）</span></h2>{_render_draft_progress(chapter)}</section>
          <section class="data-card"><h2>StateDelta 预览 <span class="muted">（待提取）</span></h2>{_render_state_delta_preview(chapter)}</section>
          <section class="data-card"><h2>RunTrace <span class="muted">（本章运行轨迹）</span></h2>{_run_trace_preview()}</section>
          <section class="data-card"><h2>成本 <span class="muted">（本章累计）</span></h2>{_cost_preview()}</section>
          <section class="data-card"><h2>恢复点</h2>{_recovery_preview()}</section>
        </div>
      </section>
"""


def render_chapter_production_aside(chapter: Chapter) -> str:
    return f"""
      <aside class="right-panel production-aside">
        <section>
          <h2>下一步风控 Gate <span class="status-pill pending">待通过 4</span></h2>
          <div class="gate-list">
            {_gate_item("情节连贯性", "检查与前文与可信设定一致性", "中")}
            {_gate_item("角色行为动机", "检查角色行为与动机合理性", "中")}
            {_gate_item("伏笔推进合理性", "检查伏笔推进是否得当", "低")}
            {_gate_item("世界规则一致性", "检查是否违反世界规则", "低")}
          </div>
        </section>
        <section class="current-run">
          <h2>当前正在</h2>
          <p><span class="status-dot warn"></span>生成草稿（AI 撰写中）</p>
          <dl>
            <dt>开始时间</dt><dd>今天 14:32</dd>
            <dt>运行时长</dt><dd>00:01:28</dd>
            <dt>预计剩余</dt><dd>00:00:32</dd>
          </dl>
        </section>
        <form method="post" action="/run-chapter" class="compact-form">
          <input type="hidden" name="chapter_id" value="{chapter.id}">
          <button type="submit">继续运行</button>
          <button class="secondary" type="button">暂停</button>
        </form>
      </aside>
"""


def render_review_tabs() -> str:
    return """
      <nav class="review-tabs" aria-label="章节审核">
        <span class="active">审计问题</span>
        <span>StateDelta 待验证</span>
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
          <p>RunTrace 完成 <span>已归档</span></p>
        </div>
        <section class="data-card"><h2>成本</h2>{_cost_preview(total="¥0.90")}</section>
        <section class="data-card"><h2>恢复点</h2><p>第 {chapter.number:02d} 章已写入可信设定，可安全恢复到此状态。</p></section>
      </section>
"""


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
        f'<div class="model-field"><label>{label}</label><div class="input-shell">'
        f'<input name="{name}" type="{input_type}" value="{value}" '
        f'placeholder="{html.escape(placeholder, quote=True)}"{" required" if required else ""}>'
        f"{suffix_html}</div></div>"
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


def _risk_item(level: str, title: str, copy: str) -> str:
    level_class = {"高": "high", "中": "medium", "低": "low"}.get(level, "low")
    return (
        f'<article><span class="risk-badge {level_class}">{html.escape(level)}</span>'
        f"<div><strong>{html.escape(title)}</strong><p>{html.escape(copy)}</p></div>"
        '<a class="button secondary" href="#">查看</a></article>'
    )


def _render_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "<p>—</p>"
        return "<ul>" + "".join(f"<li>{_render_nested(item)}</li>" for item in value[:6]) + "</ul>"
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
        return "；".join(f"{_label_key(k)}：{_short_text(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "、".join(_short_text(item) for item in value)
    return _short_text(value)


def _label_key(key: object) -> str:
    labels = {
        "chapter": "章节",
        "changes": "变化",
        "detail": "内容",
        "direction": "方向",
        "from": "起点",
        "goal": "目标",
        "impact": "影响",
        "name": "名称",
        "summary": "摘要",
        "target": "对象",
        "title": "标题",
        "to": "终点",
        "type": "类型",
    }
    return html.escape(labels.get(str(key), str(key)))


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
    items = context or {
        "Canon 基线": "已锁定（v1.3）",
        "前文摘要": "前 0 章 · 3,214 字",
        "人物档案": "6 人相关",
        "地点设定": "8 处相关",
        "伏笔清单": "3 条待推进",
        "世界规则": "12 条相关",
        "写作指引": "语气：沉稳、神秘",
    }
    return _render_value(items)


def _render_draft_progress(chapter: Chapter) -> str:
    text = (
        chapter.draft_text
        or "山谷的风带着潮湿的气息，卷过石拱与残垣。罗斯握紧拳头，沿着断裂的石阶向下。远处，似有低语从雾中传来。"
    )
    return f"""
      <dl><dt>模型</dt><dd>本地模型 v2 · 32B</dd><dt>风格</dt><dd>奇幻 · 沉稳 · 探索</dd><dt>目标字数</dt><dd>2,800 字左右</dd><dt>已生成</dt><dd>{chapter.word_count or 1248} 字（68%）</dd></dl>
      <p class="draft-snippet">{html.escape(text[:120])}...</p>
"""


def _render_state_delta_preview(chapter: Chapter) -> str:
    changes = chapter.state_delta.get("changes", [])
    if not changes:
        changes = [
            "人物状态 —",
            "关系变化 —",
            "地点变化 —",
            "伏笔 —",
            "物品变化 —",
            "世界规则影响 —",
        ]
    if isinstance(changes, list):
        return (
            "<ul>" + "".join(f"<li>{_render_nested(item)}</li>" for item in changes[:6]) + "</ul>"
        )
    return _render_value(changes)


def _run_trace_preview() -> str:
    return """
      <ul class="trace-preview">
        <li><span class="status-dot done"></span>14:32:10 章节规划完成</li>
        <li><span class="status-dot done"></span>14:32:18 上下文编译完成</li>
        <li><span class="status-dot warn"></span>14:32:24 开始生成草稿</li>
      </ul>
"""


def _cost_preview(total: str = "¥1.62") -> str:
    return f"""
      <table><tbody>
        <tr><td>AI 生成</td><td>¥0.89</td></tr>
        <tr><td>AI 审计（预估）</td><td>¥0.31</td></tr>
        <tr><td>AI 修订（预估）</td><td>¥0.42</td></tr>
        <tr><td><strong>合计</strong></td><td><strong>{html.escape(total)}</strong></td></tr>
      </tbody></table>
"""


def _recovery_preview() -> str:
    return """
      <ul class="recovery-list">
        <li>当前节点：生成草稿（进度 68%）</li>
        <li>上一个节点：编译上下文（已完成）</li>
        <li>更早节点：规划本章（已完成）</li>
      </ul>
"""


def _gate_item(title: str, copy: str, level: str) -> str:
    return (
        f"<article><span class='gate-icon'>{html.escape(level)}</span>"
        f"<div><strong>{html.escape(title)}</strong><p>{html.escape(copy)}</p></div></article>"
    )
