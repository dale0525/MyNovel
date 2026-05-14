from __future__ import annotations

import html
from typing import Any

from mynovel.blueprint_candidates import BlueprintCandidate, blueprint_candidates_from_content
from mynovel.blueprint_revision import REGENERATE_BLUEPRINT_NOTES
from mynovel.domain.models import OpenBookBlueprint
from mynovel.i18n import t


def render_blueprint_review(
    blueprint: OpenBookBlueprint,
    content: dict[str, Any],
    locale: str,
) -> str:
    candidates = blueprint_candidates_from_content(content)
    selected = candidates[0] if candidates else None
    selected_title = selected.title if selected else ""
    proposals = _render_blueprint_proposal_cards(candidates, locale)
    selected_detail = _render_candidate_detail(selected, locale) if selected else ""
    detail_templates = _render_detail_templates(candidates, locale)
    return f"""
      <section class="main-panel blueprint-main" data-blueprint-review>
        <div class="panel-head">
          <div>
            <h1>{t("blueprint.review_title", locale)}</h1>
            <p>{t("blueprint.review_copy", locale)}</p>
          </div>
          <span class="status-pill pending candidate-status-banner">候选待确认 · 尚未写入可信设定</span>
        </div>
        <div class="proposal-grid">{proposals}</div>
        <section class="blueprint-selected-detail" data-blueprint-detail-panel>{selected_detail}</section>
        {detail_templates}
        {_selection_script()}
      </section>
      <aside class="right-panel blueprint-actions">
        <h2>选择后怎么处理</h2>
        <div class="blueprint-action-grid">
          <form id="blueprint-accept-form" method="post" action="/accept-blueprint" class="compact-form candidate-confirmation blueprint-confirmation-form">
            <input type="hidden" name="blueprint_id" value="{blueprint.id}">
            <input id="selected_title" name="selected_title" type="hidden" value="{html.escape(selected_title, quote=True)}">
            <h3>当前选择</h3>
            <p class="selected-title-summary" data-selected-title-label>{html.escape(selected_title or "请选择一个方案")}</p>
            <button type="submit">确认方案，进入下一步 · 可信设定定盘</button>
          </form>
          <form method="post" action="/revise-blueprint" class="compact-form action-form blueprint-revision-form">
            <input type="hidden" name="blueprint_id" value="{blueprint.id}">
            {_textarea("revision_notes", t("blueprint.revision_notes", locale), "写下你希望保留、加强或避开的方向")}
            <div class="actions">
              <button type="submit">让系统修改蓝图 · 按备注修改</button>
              <button class="secondary" type="submit" name="revision_preset" value="{html.escape(REGENERATE_BLUEPRINT_NOTES, quote=True)}">{t("blueprint.regenerate", locale)}</button>
            </div>
          </form>
        </div>
      </aside>
"""


def render_structured_blueprint(
    content: dict[str, Any],
    locale: str,
    include_title_options: bool = True,
) -> str:
    if not content:
        return ""
    sections = _detail_sections(content, locale, include_title_options=include_title_options)
    return "".join(
        f"<section class='data-card'><h3>{label}</h3>{value}</section>" for label, value in sections
    )


def _render_blueprint_proposal_cards(
    candidates: list[BlueprintCandidate],
    locale: str,
) -> str:
    if not candidates:
        return f"<section class='proposal-card'><h3>{t('blueprint.title_options', locale)}</h3><p>—</p></section>"
    labels = ["方案 A", "方案 B", "方案 C"]
    return "".join(_render_proposal_card(candidate, labels, locale) for candidate in candidates[:3])


def _render_proposal_card(
    candidate: BlueprintCandidate,
    labels: list[str],
    locale: str,
) -> str:
    selected_class = " selected" if candidate.index == 0 else ""
    aria_pressed = "true" if candidate.index == 0 else "false"
    label = labels[candidate.index] if candidate.index < len(labels) else f"方案 {candidate.index + 1}"
    content = candidate.content
    selling_points = _list_preview(content.get("selling_points"))
    central_conflict = _short_text(content.get("central_conflict") or "待确认", 80)
    protagonist = _protagonist_summary(content.get("protagonist"))
    world = _world_summary(content.get("world"))
    return f"""
        <article class="proposal-card proposal-choice-card{selected_class}" role="button" tabindex="0" data-blueprint-choice="{candidate.index}" data-selected-title="{html.escape(candidate.title, quote=True)}" aria-pressed="{aria_pressed}">
          <header><h3>{html.escape(label)}</h3><span class="status-pill pending">候选中</span></header>
          <strong class="proposal-title">{html.escape(candidate.title)}</strong>
          <p><span>{t("blueprint.central_conflict", locale)}</span>{central_conflict}</p>
          <p><span>{t("blueprint.protagonist", locale)}</span>{protagonist}</p>
          <p><span>{t("blueprint.world", locale)}</span>{world}</p>
          <div class="proposal-preview-list">{selling_points}</div>
        </article>
"""


def _render_detail_templates(candidates: list[BlueprintCandidate], locale: str) -> str:
    return "".join(
        f'<template data-blueprint-detail="{candidate.index}">{_render_candidate_detail(candidate, locale)}</template>'
        for candidate in candidates[:3]
    )


def _render_candidate_detail(candidate: BlueprintCandidate | None, locale: str) -> str:
    if candidate is None:
        return ""
    sections = _detail_sections(candidate.content, locale, include_title_options=False)
    content = "".join(
        f"<section class='data-card'><h3>{label}</h3>{value}</section>" for label, value in sections
    )
    return f"""
        <div class="blueprint-detail-heading">
          <div>
            <h2>{html.escape(candidate.title)}</h2>
            <p>当前方案详情会随上方卡片选择更新。</p>
          </div>
          <span class="status-pill trusted">已选中</span>
        </div>
        <div class="blueprint-detail-grid">{content}</div>
"""


def _detail_sections(
    content: dict[str, Any],
    locale: str,
    *,
    include_title_options: bool,
) -> list[tuple[str, str]]:
    fields = [
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
    sections = []
    for key, value in fields:
        if key == "blueprint.title_options" and not include_title_options:
            continue
        if value in (None, "", [], {}):
            continue
        sections.append((t(key, locale), _render_value(value)))
    return sections


def _selection_script() -> str:
    return """
        <script>
        (() => {
          const root = document.querySelector("[data-blueprint-review]");
          const input = document.querySelector("#selected_title");
          const label = document.querySelector("[data-selected-title-label]");
          const panel = root?.querySelector("[data-blueprint-detail-panel]");
          if (!root || !input || !panel) return;
          const cards = Array.from(root.querySelectorAll("[data-blueprint-choice]"));
          const selectBlueprintCandidate = (card) => {
            const index = card.dataset.blueprintChoice;
            const title = card.dataset.selectedTitle || "";
            const template = root.querySelector(`[data-blueprint-detail="${index}"]`);
            input.value = title;
            if (label) label.textContent = title;
            cards.forEach((item) => {
              const selected = item === card;
              item.classList.toggle("selected", selected);
              item.setAttribute("aria-pressed", selected ? "true" : "false");
            });
            if (template) panel.innerHTML = template.innerHTML;
          };
          cards.forEach((card) => {
            card.addEventListener("click", () => selectBlueprintCandidate(card));
            card.addEventListener("keydown", (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                selectBlueprintCandidate(card);
              }
            });
          });
        })();
        </script>
"""


def _textarea(name: str, label: str, placeholder: str = "") -> str:
    return (
        f'<label>{label}<textarea name="{name}" '
        f'placeholder="{html.escape(placeholder, quote=True)}"></textarea></label>'
    )


def _list_preview(value: Any) -> str:
    values = value if isinstance(value, list) else [value] if value else []
    if not values:
        return "<span>待确认</span>"
    return "".join(f"<span>{_short_text(item, 24)}</span>" for item in values[:3])


def _render_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "<p>—</p>"
        return "<ul>" + "".join(f"<li>{_render_nested(item)}</li>" for item in value[:10]) + "</ul>"
    if isinstance(value, dict):
        return (
            "<dl>"
            + "".join(f"<dt>{_label_key(key)}</dt><dd>{_render_nested(item)}</dd>" for key, item in value.items())
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
    return html.escape(_plain_key_label(key))


def _plain_key_label(key: object) -> str:
    labels = {
        "chapter": "章节",
        "direction": "方向",
        "goal": "目标",
        "hook": "钩子",
        "name": "名称",
        "premise": "前提",
        "title": "标题",
    }
    return labels.get(str(key), str(key))


def _protagonist_summary(value: Any) -> str:
    if isinstance(value, dict):
        name = _first_text(value, ("name", "title"))
        hook = _first_text(
            value,
            ("hook", "identity", "role", "archetype", "trait", "goal", "description", "detail"),
        )
        if name and hook:
            return _short_text(f"{name}：{hook}", 64)
        if name:
            return _short_text(name, 64)
    return _short_text(value or "待确认", 64)


def _world_summary(value: Any) -> str:
    if isinstance(value, dict):
        summary = _first_text(
            value,
            ("premise", "setting", "background", "worldview", "core_rule", "location", "detail", "description"),
        )
        if summary:
            return _short_text(summary, 72)
    return _short_text(value or "待确认", 72)


def _first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return _plain_text(value)
    return ""


def _plain_text(value: object) -> str:
    if isinstance(value, dict):
        parts = [
            f"{_plain_key_label(key)}：{_plain_text(item)}"
            for key, item in value.items()
            if item not in (None, "", [], {})
        ]
        return "；".join(parts)
    if isinstance(value, list):
        return "、".join(_plain_text(item) for item in value if item not in (None, "", [], {}))
    return str(value)


def _short_text(value: object, limit: int = 80) -> str:
    text = _plain_text(value)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return html.escape(text)
