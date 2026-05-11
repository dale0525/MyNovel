from __future__ import annotations

import html

from mynovel.update import UpdateCheckResult


def render_update_page(
    result: UpdateCheckResult | None = None,
    message: str | None = None,
    manifest_url: str = "",
) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>检查更新</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="update-shell">
    <header>
      <a href="/">返回工作台</a>
      <h1>检查更新</h1>
      <p>仅检查稳定版本；不会静默安装。</p>
      {f"<p class='notice'>{html.escape(message)}</p>" if message else ""}
    </header>
    <section class="panel">
      <h2>稳定版本</h2>
      <form method="post" action="/check-update">
        <label>更新元数据地址<input name="manifest_url" placeholder="https://example.test/update.json" required></label>
        <button type="submit">检查更新</button>
      </form>
    </section>
    {_render_result(result, manifest_url)}
  </main>
</body>
</html>
"""


def _render_result(result: UpdateCheckResult | None, manifest_url: str) -> str:
    if result is None:
        return ""
    if not result.available:
        return "<section class='panel'><h2>当前已是可用版本</h2><p>没有需要提示的稳定更新。</p></section>"
    return f"""
    <section class="panel">
      <h2>发现新版本</h2>
      <dl>
        <dt>版本</dt><dd>{html.escape(result.version or "")}</dd>
        <dt>变更摘要</dt><dd>{html.escape(result.notes)}</dd>
        <dt>下载大小</dt><dd>{html.escape(result.size_label)}</dd>
        <dt>发布时间</dt><dd>{html.escape(result.published_at or "")}</dd>
        <dt>校验值</dt><dd>{html.escape(result.sha256 or "")}</dd>
      </dl>
      <a class="button" href="{html.escape(result.url or "", quote=True)}">下载更新</a>
      <form method="post" action="/check-update">
        <input type="hidden" name="skipped_version" value="{html.escape(result.version or "", quote=True)}">
        <input type="hidden" name="manifest_url" value="{html.escape(manifest_url, quote=True)}">
        <button class="secondary" type="submit">跳过当前版本</button>
      </form>
    </section>
"""


def _css() -> str:
    return """
    :root{--bg:#f7f8f4;--panel:#fffefa;--ink:#1d2822;--muted:#68756d;--line:#dbe2d8;--accent:#426f4e}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:0}.update-shell{max-width:860px;margin:0 auto;padding:28px}a{color:var(--accent);text-decoration:none}h1{margin:8px 0;font-size:28px}h2{margin:0 0 12px;font-size:18px}p{color:var(--muted);line-height:1.6}.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;margin-top:12px}form{display:grid;gap:10px;margin-top:10px}label{display:grid;gap:6px;color:var(--muted);font-size:13px}input{border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);font:inherit;min-height:40px;padding:9px 11px}button,.button{display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:0;border-radius:7px;background:var(--accent);color:#fff;font:inherit;font-weight:650;padding:9px 14px}.secondary{background:#fff;color:var(--ink);border:1px solid var(--line)}dl{display:grid;grid-template-columns:96px 1fr;gap:8px 12px}dt{color:var(--muted)}dd{margin:0}.notice{color:#c47a16}
    """
