from __future__ import annotations

import html
from typing import Any

from mynovel.domain.models import (
    Book,
    Chapter,
    DeconstructionStudy,
    QualitySnapshot,
    StyleAsset,
)
from mynovel.ui_shell import PipelineStep, render_app_page, render_pipeline, render_project_sidebar


def render_quality_center(
    book: Book,
    style_assets: list[StyleAsset],
    studies: list[DeconstructionStudy],
    latest_snapshot: QualitySnapshot | None,
    cost_strategy: dict[str, Any] | None,
    chapters: list[Chapter] | None = None,
    message: str | None = None,
) -> str:
    strategy = cost_strategy or {}
    main = f"""
      {render_project_sidebar(book, chapters or [])}
      <section class="main-panel quality-main">
        <div class="panel-head">
          <div>
            <h1>质量增强</h1>
            <p>{html.escape(book.title)} · 风格资产、拆书学习、长期质量分析和成本策略。</p>
          </div>
          <a class="button secondary" href="/book/{book.id}">返回项目</a>
        </div>
        <div class="quality-grid">
      <article class="quality-card">
        <h2>风格资产</h2>
        {_render_style_assets(style_assets)}
        <form method="post" action="/style-asset">
          <input type="hidden" name="book_id" value="{book.id}">
          <label>资产名称<input name="name" required></label>
          <label>来源标题<input name="source_title"></label>
          <label>参考片段<textarea name="reference_text" required></textarea></label>
          <button type="submit">保存风格资产</button>
        </form>
      </article>
      <article class="quality-card">
        <h2>拆书学习</h2>
        {_render_studies(studies)}
        <form method="post" action="/deconstruct-reference">
          <input type="hidden" name="book_id" value="{book.id}">
          <label>参考标题<input name="source_title" required></label>
          <label>参考正文<textarea name="reference_text" required></textarea></label>
          <button type="submit">生成拆书笔记</button>
        </form>
      </article>
      <article class="quality-card">
        <h2>长期质量分析</h2>
        {_render_snapshot(latest_snapshot)}
        <form method="post" action="/quality-snapshot">
          <input type="hidden" name="book_id" value="{book.id}">
          <button type="submit">刷新质量分析</button>
        </form>
      </article>
      <article class="quality-card">
        <h2>成本策略</h2>
        {_render_strategy(strategy)}
      </article>
        </div>
      </section>
      <aside class="right-panel">
        <h2>质量关卡</h2>
        <p>先处理高风险审计问题，再继续批量生产。</p>
        <a class="button" href="/book/{book.id}">返回项目</a>
      </aside>
"""
    return render_app_page(
        title=f"{book.title} · 质量增强",
        active="analysis",
        main=main,
        bottom=render_pipeline(
            [
                PipelineStep(
                    "style", "风格资产", "done" if style_assets else "current", "当前阶段", "1"
                ),
                PipelineStep("study", "拆书学习", "pending", "待开始", "2"),
                PipelineStep("analysis", "质量分析", "pending", "待开始", "3"),
                PipelineStep("cost", "成本策略", "pending", "待开始", "4"),
            ]
        ),
        message=message,
        eyebrow="质量增强",
        nav_book_id=book.id,
    )


def _render_style_assets(assets: list[StyleAsset]) -> str:
    if not assets:
        return "<p>还没有风格资产。</p>"
    return "<ul>" + "".join(_style_asset_item(asset) for asset in assets[-5:]) + "</ul>"


def _style_asset_item(asset: StyleAsset) -> str:
    rules = asset.guidance.get("style_rules", [])
    return (
        f"<li><strong>{html.escape(asset.name)}</strong>"
        f"<p>{html.escape(asset.source_title or asset.source_excerpt)}</p>"
        f"<em>{html.escape('；'.join(str(rule) for rule in rules[:2]))}</em></li>"
    )


def _render_studies(studies: list[DeconstructionStudy]) -> str:
    if not studies:
        return "<p>还没有拆书笔记。</p>"
    return "<ul>" + "".join(_study_item(study) for study in studies[-5:]) + "</ul>"


def _study_item(study: DeconstructionStudy) -> str:
    beats = "；".join(str(item.get("beat", "")) for item in study.beat_map[:4])
    moves = "；".join(str(item) for item in study.craft_notes.get("reusable_moves", [])[:2])
    return (
        f"<li><strong>{html.escape(study.source_title)}</strong>"
        f"<p>{html.escape(beats)}</p><em>{html.escape(moves)}</em></li>"
    )


def _render_snapshot(snapshot: QualitySnapshot | None) -> str:
    if snapshot is None:
        return "<p>还没有长期质量分析。</p>"
    metrics = snapshot.metrics
    items = [
        ("质量分", snapshot.score),
        ("已批准章节", metrics.get("accepted_chapters", 0)),
        ("待审核章节", metrics.get("review_backlog", 0)),
        ("高风险问题", metrics.get("high_risk_issues", 0)),
        ("估算字符", metrics.get("estimated_chars", 0)),
    ]
    metric_html = "".join(
        f"<div><strong>{html.escape(str(value))}</strong><span>{label}</span></div>"
        for label, value in items
    )
    recommendations = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in snapshot.recommendations
    )
    return f"<div class='metrics'>{metric_html}</div><ul>{recommendations}</ul>"


def _render_strategy(strategy: dict[str, Any]) -> str:
    if not strategy:
        return "<p>刷新质量分析后生成成本策略。</p>"
    return (
        f"<div class='strategy'><strong>{html.escape(str(strategy.get('mode', 'balanced')))}</strong>"
        f"<p>建议批量数：{html.escape(str(strategy.get('batch_limit', 1)))}</p>"
        f"<p>{html.escape(str(strategy.get('context_policy', '')))}</p></div>"
    )


def _css() -> str:
    return """
    :root{--bg:#f7f8f4;--panel:#fffefa;--ink:#1d2822;--muted:#68756d;--line:#dbe2d8;--accent:#426f4e}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}
    .quality-shell{padding:24px}.topbar{display:flex;justify-content:space-between;gap:20px;margin-bottom:18px}.topbar a{color:var(--accent);text-decoration:none}.notice{color:#c47a16}
    h1{margin:6px 0 8px;font-size:28px}h2{margin:0 0 12px;font-size:18px}p{margin:0 0 12px;color:var(--muted);line-height:1.6}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px}
    ul{padding-left:20px}li{margin:8px 0;line-height:1.5}em{display:block;color:var(--muted);font-style:normal}form{display:grid;gap:10px;border-top:1px solid var(--line);padding-top:12px;margin-top:12px}label{display:grid;gap:6px;color:var(--muted);font-size:13px}input,textarea{border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);font:inherit;min-height:40px;padding:9px 11px}textarea{min-height:120px;resize:vertical}button{min-height:40px;border:0;border-radius:7px;background:var(--accent);color:#fff;font:inherit;font-weight:650;padding:9px 14px}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metrics div,.strategy{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px}.metrics strong{display:block;font-size:24px}.metrics span{color:var(--muted);font-size:13px}
    @media(max-width:900px){.grid{grid-template-columns:1fr}.topbar{display:block}}
    """
