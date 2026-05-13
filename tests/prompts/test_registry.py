from pathlib import Path

from mynovel.prompts.registry import load_prompt_asset, load_prompt_by_id, render_prompt_messages


def test_prompt_asset_requires_source_metadata(tmp_path: Path) -> None:
    path = tmp_path / "prompt.yaml"
    path.write_text(
        """
id: open_book
name: Open Book
version: "0.1.0"
purpose: Create initial book canon
source: original
source_license: Apache-2.0
template: "Write a book plan for {{ idea }}"
""".strip(),
        encoding="utf-8",
    )

    asset = load_prompt_asset(path)

    assert asset.id == "open_book"
    assert asset.source_license == "Apache-2.0"


def test_chapter_pipeline_prompt_asset_declares_all_stage_prompts() -> None:
    asset = load_prompt_asset(Path("src/mynovel/prompts/assets/chapter_pipeline.yaml"))

    assert asset.id == "chapter_pipeline"
    assert asset.version == "0.1.0"
    assert asset.source_license == "Apache-2.0"
    assert asset.output_schema["stages"] == [
        "chapter_plan",
        "chapter_context",
        "chapter_draft",
        "chapter_state_extract",
        "chapter_audit",
        "chapter_revise",
    ]


def test_runtime_prompt_registry_loads_and_renders_stage_prompt() -> None:
    asset = load_prompt_by_id("chapter_plan")
    messages = render_prompt_messages(asset, {"chapter_title": "离开的召唤"})

    assert asset.id == "chapter_plan"
    assert asset.source_license == "Apache-2.0"
    assert messages[0]["role"] == "system"
    assert "离开的召唤" in messages[1]["content"]


def test_canon_proposal_revision_prompt_declares_json_contract() -> None:
    asset = load_prompt_by_id("canon_proposal_revision")

    assert asset.id == "canon_proposal_revision"
    assert asset.source_license == "Apache-2.0"
    assert "changed_sections" in asset.output_schema["required"]
    assert "blocked_sections" in asset.output_schema["required"]
