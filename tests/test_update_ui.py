from mynovel.update import UpdateCheckResult
from mynovel.update_views import render_update_page


def test_update_page_renders_stable_check_form() -> None:
    page = render_update_page()

    assert "检查更新" in page
    assert "稳定版本" in page
    assert 'action="/check-update"' in page
    assert 'name="manifest_url"' in page
    assert "beta" not in page.lower()
    assert "nightly" not in page.lower()


def test_update_page_renders_available_update_and_skip_action() -> None:
    page = render_update_page(
        UpdateCheckResult(
            available=True,
            version="0.2.0",
            url="MyNovel-macos-arm64",
            sha256="abc123",
            notes="修复恢复流程。",
            published_at="2026-05-11T00:00:00Z",
            size_label="12.0 MB",
        )
    )

    assert "发现新版本" in page
    assert "0.2.0" in page
    assert "修复恢复流程。" in page
    assert "12.0 MB" in page
    assert 'name="skipped_version" value="0.2.0"' in page
