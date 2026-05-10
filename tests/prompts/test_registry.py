from pathlib import Path

from mynovel.prompts.registry import load_prompt_asset


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
