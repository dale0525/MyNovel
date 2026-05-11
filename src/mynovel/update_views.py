from __future__ import annotations

import html

from mynovel.update import StagedUpdateInstall, UpdateCheckResult
from mynovel.ui_shell import PipelineStep, render_app_page, render_pipeline


def render_update_page(
    result: UpdateCheckResult | None = None,
    message: str | None = None,
    manifest_url: str = "",
    staged_install: StagedUpdateInstall | None = None,
) -> str:
    main = f"""
    <section class="main-panel single update-main">
      <div class="panel-head">
        <div>
          <h1>检查更新</h1>
          <p>仅检查稳定版本；不会静默安装。</p>
        </div>
        <a class="button secondary" href="/">返回工作台</a>
      </div>
      <h2>稳定版本</h2>
      <form method="post" action="/check-update">
        <label>更新元数据地址<input name="manifest_url" placeholder="https://example.test/update.json" required></label>
        <button type="submit">检查更新</button>
      </form>
    </section>
    {_render_result(result, manifest_url)}
    {_render_staged_install(staged_install)}
"""
    return render_app_page(
        title="检查更新",
        active="settings",
        main=main,
        bottom=render_pipeline(
            [
                PipelineStep("check", "检查更新", "current", "当前阶段", "1"),
                PipelineStep("download", "准备安装", "pending", "待开始", "2"),
                PipelineStep("confirm", "手动确认", "pending", "待开始", "3"),
            ]
        ),
        message=message,
        eyebrow="设置",
        content_class="content-grid narrow-layout",
    )


def _render_result(result: UpdateCheckResult | None, manifest_url: str) -> str:
    if result is None:
        return ""
    if not result.available:
        return "<section class='main-panel single update-main'><h2>当前已是可用版本</h2><p>没有需要提示的稳定更新。</p></section>"
    return f"""
    <section class="main-panel single update-main">
      <h2>发现新版本</h2>
      <dl>
        <dt>版本</dt><dd>{html.escape(result.version or "")}</dd>
        <dt>变更摘要</dt><dd>{html.escape(result.notes)}</dd>
        <dt>下载大小</dt><dd>{html.escape(result.size_label)}</dd>
        <dt>发布时间</dt><dd>{html.escape(result.published_at or "")}</dd>
        <dt>校验值</dt><dd>{html.escape(result.sha256 or "")}</dd>
      </dl>
      <a class="button" href="{html.escape(result.url or "", quote=True)}">下载更新</a>
      <form method="post" action="/stage-update">
        <input type="hidden" name="manifest_url" value="{html.escape(manifest_url, quote=True)}">
        <button type="submit">下载并准备安装</button>
      </form>
      <form method="post" action="/check-update">
        <input type="hidden" name="skipped_version" value="{html.escape(result.version or "", quote=True)}">
        <input type="hidden" name="manifest_url" value="{html.escape(manifest_url, quote=True)}">
        <button class="secondary" type="submit">跳过当前版本</button>
      </form>
    </section>
"""


def _render_staged_install(staged_install: StagedUpdateInstall | None) -> str:
    if staged_install is None:
        return ""
    artifact_path = html.escape(str(staged_install.payload.get("artifact_path", "")))
    backup_path = html.escape(str(staged_install.payload.get("db_backup_path", "")))
    plan_path = html.escape(str(staged_install.plan_path))
    return f"""
    <section class="main-panel single update-main">
      <h2>更新已准备</h2>
      <p>安装包已下载并校验，数据库备份已生成。请手动确认安装。</p>
      <dl>
        <dt>安装包</dt><dd>{artifact_path}</dd>
        <dt>数据库备份</dt><dd>{backup_path}</dd>
        <dt>安装计划</dt><dd>{plan_path}</dd>
      </dl>
    </section>
"""
