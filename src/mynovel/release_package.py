from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from hashlib import sha256
from pathlib import Path

from mynovel.db import SCHEMA_VERSION


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Create unsigned native MyNovel installer assets.")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--version", default=os.environ.get("GITHUB_REF_NAME", "0.0.0"))
    parser.add_argument("--platform", default=_default_platform())
    args = parser.parse_args(argv)

    version = normalize_release_version(args.version)
    artifact = package_native_installer(args.dist, version, args.platform)
    metadata = _write_metadata(args.dist, artifact, version, args.platform)
    print(f"Packaged {artifact}")
    print(f"Wrote {metadata}")


def package_native_installer(dist_dir: Path, version: str, platform_name: str) -> Path:
    version = normalize_release_version(version)
    executable = _find_executable(dist_dir, platform_name)
    if platform_name.startswith("macos"):
        return _package_macos_dmg(dist_dir, executable, platform_name)
    if platform_name == "windows-x64":
        return _package_windows_msi(dist_dir, executable, version)
    raise ValueError(f"Unsupported release platform: {platform_name}")


def _package_macos_dmg(dist_dir: Path, executable: Path, platform_name: str) -> Path:
    app_dir = dist_dir / "MyNovel.app"
    macos_dir = app_dir / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, macos_dir / "MyNovel")
    (app_dir / "Contents" / "Info.plist").write_text(_info_plist(), encoding="utf-8")
    dmg_path = dist_dir / f"MyNovel-{platform_name}.dmg"
    if dmg_path.exists():
        dmg_path.unlink()
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            "MyNovel",
            "-srcfolder",
            str(app_dir),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ],
        check=True,
    )
    return dmg_path


def _package_windows_msi(dist_dir: Path, executable: Path, version: str) -> Path:
    wix_file = dist_dir / "MyNovel.wxs"
    msi_path = dist_dir / "MyNovel-windows-x64.msi"
    wix_file.write_text(_wix_source(executable, version), encoding="utf-8")
    subprocess.run(["wix", "build", str(wix_file), "-o", str(msi_path)], check=True)
    return msi_path


def _write_metadata(dist_dir: Path, artifact: Path, version: str, platform_name: str) -> Path:
    version = normalize_release_version(version)
    digest = sha256(artifact.read_bytes()).hexdigest()
    checksum_path = dist_dir / f"checksums-{platform_name}.sha256"
    checksum_path.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
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
    )
    return manifest_path


def _find_executable(dist_dir: Path, platform_name: str) -> Path:
    candidates = [dist_dir / "MyNovel.exe", dist_dir / "MyNovel"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"MyNovel executable not found in {dist_dir} for {platform_name}.")


def _default_platform() -> str:
    machine = platform.machine().lower()
    system = platform.system().lower()
    if system == "darwin":
        return "macos-arm64" if machine in {"arm64", "aarch64"} else "macos-x64"
    if system == "windows":
        return "windows-x64"
    raise ValueError("Native packaging is only configured for macOS and Windows.")


def normalize_release_version(version: str) -> str:
    version = version.removeprefix("refs/tags/")
    if version.startswith("v"):
        return version[1:]
    return version


def _info_plist() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>MyNovel</string>
  <key>CFBundleIdentifier</key><string>com.mynovel.app</string>
  <key>CFBundleName</key><string>MyNovel</string>
  <key>CFBundlePackageType</key><string>APPL</string>
</dict>
</plist>
"""


def _wix_source(executable: Path, version: str) -> str:
    version = normalize_release_version(version)
    normalized_version = ".".join((version.split(".") + ["0", "0", "0"])[:3])
    return f"""<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Package Name="MyNovel" Manufacturer="MyNovel" Version="{normalized_version}" UpgradeCode="8E99D341-7B02-4CB7-90E3-76BE6411B2F1">
    <MajorUpgrade DowngradeErrorMessage="A newer version of MyNovel is already installed." />
    <MediaTemplate EmbedCab="yes" />
    <StandardDirectory Id="ProgramFilesFolder">
      <Directory Id="INSTALLFOLDER" Name="MyNovel">
        <Component Id="MyNovelExe" Guid="*">
          <File Id="MyNovelExeFile" Source="{executable}" KeyPath="yes" />
        </Component>
      </Directory>
    </StandardDirectory>
    <Feature Id="DefaultFeature" Title="MyNovel" Level="1">
      <ComponentRef Id="MyNovelExe" />
    </Feature>
  </Package>
</Wix>
"""


if __name__ == "__main__":
    main()
