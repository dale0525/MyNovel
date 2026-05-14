from __future__ import annotations

import html
from typing import Sequence

from mynovel.i18n import DEFAULT_LOCALE, t


def render_open_book_page_main(
    *,
    submit_disabled: bool,
    genre_options: Sequence[str],
    audience_options: Sequence[str],
    default_target_words: int,
    default_chapter_words: int,
    locale: str = DEFAULT_LOCALE,
) -> str:
    return f"""
      {render_open_book_step_rail(locale)}
      <section class="main-panel open-book-focus-panel">
        <div class="panel-head">
          <div>
            <p class="section-kicker">{t("new_book.focus_kicker", locale)}</p>
            <h1>{t("new_book.focus_title", locale)}</h1>
            <p>{t("new_book.focus_copy", locale)}</p>
          </div>
          <span class="status-pill trusted">{t("new_book.focus_badge", locale)}</span>
        </div>
        {render_open_book_form(
            submit_disabled=submit_disabled,
            genre_options=genre_options,
            audience_options=audience_options,
            default_target_words=default_target_words,
            default_chapter_words=default_chapter_words,
            locale=locale,
        )}
      </section>
      {render_open_book_preview_sidebar(locale)}
"""


def render_open_book_step_rail(locale: str = DEFAULT_LOCALE) -> str:
    return f"""
      <aside class="side-panel book-wizard step-rail">
        <h2>{t("new_book.title", locale)}</h2>
        <p>{t("new_book.subtitle", locale)}</p>
        <ol class="step-list vertical-flow">
          <li class="active"><strong>{t("new_book.step_settings", locale)}</strong><span>{t("new_book.step_settings_copy", locale)}</span></li>
          <li><strong>{t("new_book.step_proposal", locale)}</strong><span>{t("new_book.step_proposal_copy", locale)}</span></li>
          <li><strong>{t("new_book.step_foundation", locale)}</strong><span>{t("new_book.step_foundation_copy", locale)}</span></li>
        </ol>
        <p class="hint-box">{t("new_book.step_hint", locale)}</p>
      </aside>
"""


def render_open_book_form(
    *,
    submit_disabled: bool,
    genre_options: Sequence[str],
    audience_options: Sequence[str],
    default_target_words: int,
    default_chapter_words: int,
    locale: str = DEFAULT_LOCALE,
) -> str:
    disabled_attr = " disabled" if submit_disabled else ""
    return f"""
      <form method="post" action="/open-book" class="single-focus-form">
        <label class="idea-field">{t("new_book.focus_title", locale)}
          <textarea name="idea" placeholder="{t("book.idea_placeholder", locale)}" required></textarea>
        </label>
        <details class="optional-inputs">
          <summary>{t("new_book.optional_title", locale)}</summary>
          <div class="optional-input-grid">
            {_render_optional_input_fields(
                genre_options=genre_options,
                audience_options=audience_options,
                default_target_words=default_target_words,
                default_chapter_words=default_chapter_words,
                locale=locale,
            )}
          </div>
        </details>
        <div class="actions">
          <a class="button secondary" href="/">{t("action.back", locale)}</a>
          <button type="submit"{disabled_attr}>{t("new_book.generate", locale)}</button>
        </div>
      </form>
"""


def render_open_book_preview_sidebar(locale: str = DEFAULT_LOCALE) -> str:
    return f"""
      <aside class="right-panel generated-preview open-book-preview">
        <h2>{t("new_book.preview_title", locale)}</h2>
        <p>{t("new_book.preview_copy", locale)}</p>
        <div class="generation-card-list">
          {_generation_card("书名候选", "给你几种不同气质的书名方向。")}
          {_generation_card("核心卖点", "提炼这本书最吸引读者的看点。")}
          {_generation_card("主角与起点", "明确主角的初始状态和第一步冲突。")}
          {_generation_card("世界观抓手", "把世界规则和故事入口先搭起来。")}
          {_generation_card("读者承诺", "说明这本书会稳定提供什么体验。")}
          {_generation_card("前 10 章方向", "给出前期开篇节奏和关键事件。")}
        </div>
      </aside>
"""


def _render_optional_input_fields(
    *,
    genre_options: Sequence[str],
    audience_options: Sequence[str],
    default_target_words: int,
    default_chapter_words: int,
    locale: str = DEFAULT_LOCALE,
) -> str:
    return (
        _select("genre", t("book.genre", locale), t("book.ai_choice", locale), genre_options)
        + _select("audience", t("book.audience", locale), t("book.ai_choice", locale), audience_options)
        + _input(
            "target_word_count",
            t("new_book.target_word_count", locale),
            str(default_target_words),
            "number",
        )
        + _input(
            "chapter_word_count",
            t("new_book.chapter_word_count", locale),
            str(default_chapter_words),
            "number",
        )
        + _input(
            "selling_points",
            t("book.selling_points", locale),
            "",
            "text",
            "例如：逆袭反转、智商碾压、群像高燃等（可自由描述）",
        )
        + _input(
            "constraints",
            t("book.constraints", locale),
            "",
            "text",
            "例如：不写恋爱、不写虐主、不出现玄幻设定等（可自由描述）",
        )
    )


def _generation_card(title: str, copy: str) -> str:
    return (
        '<section class="generation-card">'
        f"<span aria-hidden='true'>◇</span><div><strong>{html.escape(title)}</strong>"
        f"<p>{html.escape(copy)}</p></div></section>"
    )


def _input(
    name: str,
    label: str,
    value: str = "",
    input_type: str = "text",
    placeholder: str = "",
) -> str:
    return (
        f'<label>{html.escape(label)}<input name="{html.escape(name, quote=True)}" '
        f'type="{html.escape(input_type, quote=True)}" value="{html.escape(value, quote=True)}" '
        f'placeholder="{html.escape(placeholder, quote=True)}"></label>'
    )


def _select(name: str, label: str, empty_label: str, options: Sequence[str]) -> str:
    option_html = [f'<option value="">{html.escape(empty_label)}</option>']
    option_html.extend(
        f'<option value="{html.escape(option, quote=True)}">{html.escape(option)}</option>'
        for option in options
    )
    return (
        f'<label>{html.escape(label)}<select name="{html.escape(name, quote=True)}">'
        f'{"".join(option_html)}</select></label>'
    )
