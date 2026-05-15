import { useState } from "react";

import { ApiError, postJson } from "@/lib/api";
import { navigateTo } from "@/lib/navigation";
import type { BookPayload } from "@/lib/types";

type ImportResponse = {
  book: BookPayload;
  redirectTo: string;
};

export function ImportBookPage() {
  const [projectJson, setProjectJson] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const response = await postJson<ImportResponse>("/api/books/import", { projectJson });
      navigateTo(response.redirectTo);
    } catch (submitError) {
      setError(submitError instanceof ApiError ? submitError.message : "导入项目失败。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="workbench-page" aria-labelledby="import-book-title">
      <div className="workbench-hero">
        <p className="eyebrow">Import</p>
        <h1 id="import-book-title">导入项目</h1>
        <p className="lede">粘贴从 MyNovel 导出的 JSON，系统会重建作品、可信设定和已接受章节。</p>
      </div>

      <form className="workbench-panel open-book-form" onSubmit={handleSubmit}>
        {error ? (
          <p className="setup-message" role="alert">
            {error}
          </p>
        ) : null}
        <label className="provider-field">
          项目 JSON
          <textarea
            onChange={(event) => setProjectJson(event.target.value)}
            placeholder='{"book":{"title":"星港遗梦"},"chapters":[]}'
            required
            value={projectJson}
          />
        </label>
        <button className="workbench-action-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "导入中..." : "导入项目"}
        </button>
      </form>
    </section>
  );
}
