from pathlib import Path

import yaml
from pydantic import BaseModel, Field


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
