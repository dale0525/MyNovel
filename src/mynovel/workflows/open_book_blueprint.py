from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session

from mynovel.domain.models import BlueprintStatus, OpenBookBlueprint
from mynovel.domain.repositories import add_open_book_blueprint

REQUIRED_BLUEPRINT_FIELDS = {
    "title_options",
    "genre",
    "audience",
    "selling_points",
    "protagonist",
    "world",
    "central_conflict",
    "reader_promises",
    "chapter_directions",
}


def parse_blueprint_json(raw_text: str) -> dict[str, Any]:
    text = _strip_code_fence(raw_text.strip())
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Blueprint response must be a JSON object.")

    missing = sorted(REQUIRED_BLUEPRINT_FIELDS - set(data))
    if missing:
        raise ValueError(f"Blueprint response missing fields: {', '.join(missing)}")

    return data


def build_blueprint_messages(
    idea: str,
    previous_blueprint: dict[str, Any] | None = None,
    revision_notes: str | None = None,
) -> list[dict[str, str]]:
    system_prompt = (
        "你是网文开书导演。根据作者的一句话想法，生成可多轮修改的开书蓝图。"
        "必须只输出 JSON，不要 Markdown，不要解释。"
    )
    schema_prompt = (
        "JSON 字段必须包含：title_options, genre, audience, selling_points, protagonist, "
        "world, central_conflict, reader_promises, chapter_directions。"
        "title_options、selling_points、reader_promises、chapter_directions 使用数组；"
        "protagonist 和 world 使用对象。"
        "如果用户没有明确题材、目标读者或卖点，请根据一句灵感自行生成，不要反问。"
    )
    user_payload: dict[str, Any] = {"idea": idea}
    if previous_blueprint is not None:
        user_payload["previous_blueprint"] = previous_blueprint
    if revision_notes:
        user_payload["revision_notes"] = revision_notes

    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"{schema_prompt}\n{json.dumps(user_payload, ensure_ascii=False)}",
        },
    ]


def extract_chat_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not choices:
        raise ValueError("Chat completion response has no choices.")
    content = choices[0].get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Chat completion response has no message content.")
    return content


def create_blueprint_job(
    session: Session,
    idea: str,
    version: int,
    instruction: str | None,
    parent_id: int | None,
) -> OpenBookBlueprint:
    return add_open_book_blueprint(
        session,
        OpenBookBlueprint(
            parent_id=parent_id,
            idea=idea,
            version=version,
            status=BlueprintStatus.PENDING,
            instruction=instruction,
            content={},
            raw_response="",
        ),
    )


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text
