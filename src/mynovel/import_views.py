from __future__ import annotations

from mynovel.ui_shell import PipelineStep, render_app_page, render_pipeline


def render_import_project_page(message: str | None = None) -> str:
    main = """
      <section class="main-panel single import-project-panel">
        <div class="panel-head">
          <div>
            <h1>导入项目</h1>
            <p>粘贴从 MyNovel 导出的 JSON，系统会恢复书籍、可信设定和已批准章节。</p>
          </div>
          <a class="button secondary" href="/">返回工作台</a>
        </div>
        <form method="post" action="/books/import" class="compact-form import-project-form">
          <label for="project_json">项目 JSON</label>
          <textarea id="project_json" name="project_json" placeholder="粘贴从 MyNovel 导出的 JSON"></textarea>
          <div class="actions">
            <button type="submit">导入项目</button>
          </div>
        </form>
      </section>
"""
    return render_app_page(
        title="导入项目",
        active="workspace",
        main=main,
        message=message,
        bottom=_import_pipeline(),
        content_class="content-grid narrow-layout",
    )


def _import_pipeline() -> str:
    steps = [
        PipelineStep("import", "导入", "current", "当前阶段", "⇧"),
        PipelineStep("canon", "恢复可信设定", "pending", "待开始", "◇"),
        PipelineStep("chapters", "恢复章节", "pending", "待开始", "▤"),
        PipelineStep("workspace", "进入工作台", "pending", "待开始", "⌂"),
    ]
    return render_pipeline(steps, title="导入流水线")
