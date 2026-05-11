from mynovel.update import UpdateManifest, check_for_update


def test_update_manifest_reports_newer_stable_release() -> None:
    manifest = UpdateManifest(
        channel="stable",
        version="0.2.0",
        url="https://example.test/MyNovel.dmg",
        sha256="abc123",
        notes="修复章节恢复。",
        published_at="2026-05-11T00:00:00Z",
        size_bytes=123456,
    )

    result = check_for_update("0.1.0", manifest)

    assert result.available is True
    assert result.version == "0.2.0"
    assert result.notes == "修复章节恢复。"
    assert result.size_label == "120.6 KB"


def test_update_manifest_ignores_current_or_skipped_version() -> None:
    manifest = UpdateManifest(
        channel="stable",
        version="0.2.0",
        url="https://example.test/MyNovel.dmg",
        sha256="abc123",
        notes="修复章节恢复。",
    )

    assert check_for_update("0.2.0", manifest).available is False
    assert check_for_update("0.1.0", manifest, skipped_version="0.2.0").available is False
