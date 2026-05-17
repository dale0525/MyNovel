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
      const payload = await postJson<unknown>("/api/books/import", { projectJson });
      const response = parseImportResponse(payload);
      if (!response) {
        throw new Error("导入结果格式无效。");
      }
      navigateTo(response.redirectTo);
    } catch (submitError) {
      setError(errorMessage(submitError, "导入项目失败。"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="workbench-page" aria-labelledby="import-book-title">
      <div className="workbench-hero">
        <p className="eyebrow">导入</p>
        <h1 id="import-book-title">导入项目</h1>
        <p className="lede">粘贴从本工具导出的项目数据，系统会重建作品、可信设定和已接受章节。</p>
      </div>

      <form className="workbench-panel open-book-form" onSubmit={handleSubmit}>
        {error ? (
          <p className="setup-message" role="alert">
            {error}
          </p>
        ) : null}
        <label className="provider-field">
          项目数据
          <textarea
            onChange={(event) => setProjectJson(event.target.value)}
            placeholder='{"作品":{"标题":"星港遗梦"},"章节":[]}'
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

function parseImportResponse(payload: unknown): ImportResponse | null {
  if (!isRecord(payload) || !isBookPayload(payload.book) || !isSafeAppPath(payload.redirectTo)) {
    return null;
  }
  return payload as ImportResponse;
}

function isBookPayload(value: unknown): value is BookPayload {
  return (
    isRecord(value) &&
    (typeof value.id === "number" || value.id === null) &&
    typeof value.title === "string" &&
    typeof value.genre === "string" &&
    typeof value.audience === "string" &&
    typeof value.status === "string" &&
    (typeof value.premise === "string" || value.premise === null)
  );
}

function isSafeAppPath(value: unknown): value is string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//");
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
