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

BLUEPRINT_FIELD_LABELS = {
    "title_options": "书名候选",
    "genre": "题材",
    "audience": "目标读者",
    "selling_points": "卖点",
    "protagonist": "主角",
    "world": "世界基础",
    "central_conflict": "核心冲突",
    "reader_promises": "读者承诺",
    "chapter_directions": "章节方向",
}


def parse_blueprint_json(raw_text: str) -> dict[str, Any]:
    text = _strip_code_fence(raw_text.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("蓝图返回格式无效。") from error
    if not isinstance(data, dict):
        raise ValueError("蓝图返回格式无效。")

    missing = sorted(REQUIRED_BLUEPRINT_FIELDS - set(data))
    if missing:
        missing_labels = "、".join(BLUEPRINT_FIELD_LABELS.get(field, field) for field in missing)
        raise ValueError(f"蓝图返回缺少字段：{missing_labels}")

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
        "同时建议返回 candidates 数组，长度与 title_options 一致；每个 candidates 项必须包含 title，"
        "并可覆盖 genre, audience, selling_points, protagonist, world, central_conflict, "
        "reader_promises, chapter_directions，用于呈现真正不同的开书方案；"
        "chapter_directions 必须恰好 10 项，分别对应第1章到第10章，"
        "每项使用 {title, goal} 对象，不要使用第1-3章、第4-8章这类范围规划；"
        "protagonist 和 world 使用对象。"
        "如果用户没有明确题材、目标读者或卖点，请根据一句灵感自行生成，不要反问。"
        "如果用户提供全书目标字数或单章目标字数，必须把它们作为规划约束。"
    )
    user_payload: dict[str, Any] = {"idea": idea}
    if previous_blueprint is not None:
        schema_prompt += (
            "修订模式：必须以上一版蓝图为基础响应 revision_notes。"
            "除非修改意见明确要求改变，否则保留题材、目标读者、主角身份、世界基础和核心冲突；"
            "可以扩大书名候选、卖点包装、章节方向和读者承诺的差异。"
            "不要退回只根据一句灵感重新开书。"
        )
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
