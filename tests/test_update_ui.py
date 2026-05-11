from pathlib import Path

from mynovel.update import StagedUpdateInstall, UpdateCheckResult
from mynovel.update_views import render_update_page


def test_update_page_renders_stable_check_form() -> None:
    page = render_update_page()

    assert 'class="app-shell"' in page
    assert "检查更新" in page
    assert "稳定版本" in page
    assert 'action="/check-update"' in page
    assert 'name="manifest_url"' in page
    assert "工作台" in page
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
    assert 'action="/stage-update"' in page
    assert 'name="skipped_version" value="0.2.0"' in page


def test_update_page_renders_staged_install_plan_without_silent_install() -> None:
    page = render_update_page(
        staged_install=StagedUpdateInstall(
            plan_path=Path("/tmp/updates/staged/0.2.0/install-plan.json"),
            payload={
                "artifact_path": "/tmp/updates/staged/0.2.0/MyNovel.dmg",
                "db_backup_path": "/tmp/updates/backups/mynovel.backup.sqlite",
                "requires_user_confirmation": True,
            },
        )
    )

    assert "更新已准备" in page
    assert "手动确认安装" in page
    assert "不会静默安装" in page
