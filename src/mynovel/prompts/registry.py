from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

ASSET_DIR = Path(__file__).parent / "assets"


class PromptAsset(BaseModel):
    id: str
    name: str
    version: str
    purpose: str
    source: str
    source_license: str
    template: str
    adaptation_notes: str | None = None
    model_family_hint: str | None = None
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    evaluation_notes: str | None = None


def load_prompt_asset(path: Path) -> PromptAsset:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PromptAsset.model_validate(data)


def load_prompt_by_id(prompt_id: str) -> PromptAsset:
    direct_path = ASSET_DIR / f"{prompt_id}.yaml"
    if direct_path.exists():
        return load_prompt_asset(direct_path)

    for path in ASSET_DIR.glob("*.yaml"):
        asset = load_prompt_asset(path)
        if asset.id == prompt_id:
            return asset
    raise FileNotFoundError(f"Prompt asset not found: {prompt_id}")


def render_prompt_messages(asset: PromptAsset, payload: dict[str, Any]) -> list[dict[str, str]]:
    rendered = _render_template(asset.template, payload)
    payload_text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=True).strip()
    user_content = f"{rendered}\n\n输入：\n{payload_text}" if payload_text else rendered
    return [
        {"role": "system", "content": "你是 MyNovel 的受控生产线助手，必须遵守可信状态边界。"},
        {"role": "user", "content": user_content},
    ]


class _SafeFormatPayload(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_template(template: str, payload: dict[str, Any]) -> str:
    rendered = template
    for key, value in payload.items():
        text = _format_payload_value(value)
        rendered = rendered.replace("{{ " + key + " }}", text)
        rendered = rendered.replace("{{" + key + "}}", text)
    try:
        return rendered.format_map(
            _SafeFormatPayload(
                {key: _format_payload_value(value) for key, value in payload.items()}
            )
        )
    except ValueError:
        return rendered


def _format_payload_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=True).strip()
