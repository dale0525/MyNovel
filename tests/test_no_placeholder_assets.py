from pathlib import Path


def test_repository_text_does_not_reference_removed_placeholder_title() -> None:
    placeholder = "".join(["幽", "谷", "回", "声"])
    roots = [Path("src"), Path("tests"), Path("docs"), Path("README.md")]
    offenders = []

    for root in roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if (
                path.is_dir()
                or "__pycache__" in path.parts
                or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pyc"}
            ):
                continue
            if placeholder in path.read_text(encoding="utf-8"):
                offenders.append(str(path))

    assert offenders == []
