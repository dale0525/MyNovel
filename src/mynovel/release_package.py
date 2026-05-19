from __future__ import annotations

import argparse
import json
import shutil
import sys
from hashlib import sha256
from pathlib import Path

from mynovel.db import SCHEMA_VERSION

DEFAULT_FRONTEND_DIST = Path("frontend/dist")
DEFAULT_PACKAGE_FRONTEND_DIST = Path("src/mynovel/frontend/dist")


def main(argv: list[str] | None = None) -> None:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args[:1] == ["sync-frontend-dist"]:
        _sync_frontend_dist_command(raw_args[1:])
        return
    if raw_args[:1] == ["write-metadata"]:
        _write_metadata_command(raw_args[1:])
        return

    parser = argparse.ArgumentParser(description="Manage MyNovel release helper tasks.")
    parser.add_argument("command", choices=["sync-frontend-dist", "write-metadata"])
    parser.parse_args(raw_args)


def sync_frontend_dist(
    source_dir: Path = DEFAULT_FRONTEND_DIST,
    target_dir: Path = DEFAULT_PACKAGE_FRONTEND_DIST,
) -> Path:
    if not (source_dir / "index.html").exists():
        raise FileNotFoundError(f"Frontend build output not found at {source_dir}.")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_dir)
    return target_dir


def _sync_frontend_dist_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Copy Vite dist into the Python package.")
    parser.add_argument("--source", type=Path, default=DEFAULT_FRONTEND_DIST)
    parser.add_argument("--target", type=Path, default=DEFAULT_PACKAGE_FRONTEND_DIST)
    args = parser.parse_args(argv)
    copied = sync_frontend_dist(args.source, args.target)
    print(f"Copied frontend dist to {copied}")


def _write_metadata_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Write release metadata for an installer asset.")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform", required=True)
    args = parser.parse_args(argv)

    version = normalize_release_version(args.version)
    metadata = _write_metadata(args.dist, args.artifact, version, args.platform)
    print(f"Wrote {metadata}")


def _write_metadata(dist_dir: Path, artifact: Path, version: str, platform_name: str) -> Path:
    version = normalize_release_version(version)
    digest = sha256(artifact.read_bytes()).hexdigest()
    checksum_path = dist_dir / f"checksums-{platform_name}.sha256"
    checksum_path.write_text(
        f"{digest}  {artifact.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = dist_dir / f"update-{platform_name}.json"
    manifest_path.write_text(
        json.dumps(
            {
                "channel": "stable",
                "version": version,
                "platform": platform_name,
                "url": artifact.name,
                "sha256": digest,
                "size_bytes": artifact.stat().st_size,
                "minimum_app_version": "0.1.0",
                "minimum_schema_version": SCHEMA_VERSION,
                "database_migration": {
                    "required": False,
                    "from_schema_version": SCHEMA_VERSION,
                    "to_schema_version": SCHEMA_VERSION,
                    "notes": "",
                },
                "notes": "生成更新元数据",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path


def normalize_release_version(version: str) -> str:
    version = version.removeprefix("refs/tags/")
    if version.startswith("v"):
        return version[1:]
    return version


if __name__ == "__main__":
    main()
