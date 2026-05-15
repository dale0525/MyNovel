import { useEffect, useState } from "react";

import { getJson, isAbortError } from "@/lib/api";
import type { BookPayload, BookResponse } from "@/lib/types";

type BookWorkspaceState =
  | { status: "loading"; book: null; error: null }
  | { status: "ready"; book: BookPayload; error: null }
  | { status: "error"; book: null; error: string };

type BookWorkspacePageProps = {
  bookId: number;
};

export function BookWorkspacePage({ bookId }: BookWorkspacePageProps) {
  const [state, setState] = useState<BookWorkspaceState>({
    status: "loading",
    book: null,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setState({ status: "loading", book: null, error: null });

    getJson<unknown>(`/api/books/${bookId}`, { signal: controller.signal })
      .then((payload) => {
        const parsed = parseBookResponse(payload);
        if (!cancelled) {
          if (parsed) {
            setState({ status: "ready", book: parsed.book, error: null });
          } else {
            setState({ status: "error", book: null, error: "项目数据格式无效。" });
          }
        }
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) {
          return;
        }
        if (!cancelled) {
          setState({
            status: "error",
            book: null,
            error: error instanceof Error ? error.message : "项目加载失败。",
          });
        }
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [bookId]);

  if (state.status === "loading") {
    return (
      <section className="workbench-page" aria-labelledby="book-workspace-title">
        <div className="workbench-panel" role="status">
          正在加载项目...
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="workbench-page" aria-labelledby="book-workspace-title">
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h1 id="book-workspace-title">项目加载失败</h1>
          <p>{state.error}</p>
          <a className="workbench-action-button" href="/">
            返回工作台
          </a>
        </div>
      </section>
    );
  }

  const book = state.book;

  return (
    <section className="workbench-page book-workspace-page" aria-labelledby="book-workspace-title">
      <div className="workbench-hero book-workspace-hero">
        <p className="eyebrow">Project Workspace</p>
        <h1 id="book-workspace-title">{book.title}</h1>
        <p className="book-workspace-meta">
          {book.genre} · {book.audience} · {statusLabel(book.status)}
        </p>
        <p className="lede">{book.premise ?? "这个项目还没有记录核心承诺，下一步可以先补齐故事前提。"}</p>
      </div>

      <div className="workbench-grid">
        <section className="workbench-panel">
          <div className="workbench-panel__header">
            <div>
              <p className="eyebrow">Project Pulse</p>
              <h2>项目状态</h2>
            </div>
            <a className="workbench-action-button" href="/books/new">
              再开一本
            </a>
          </div>
          <dl className="book-workspace-facts">
            <div>
              <dt>题材</dt>
              <dd>{book.genre}</dd>
            </div>
            <div>
              <dt>受众</dt>
              <dd>{book.audience}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>{statusLabel(book.status)}</dd>
            </div>
          </dl>
        </section>

        <aside className="workbench-panel workbench-next-action">
          <p className="eyebrow">Next Actions</p>
          <h2>继续生产</h2>
          <p>从章节生产、可信设定和质量复审继续推进。后续页面接入后，这里会展示具体待办。</p>
          <div className="book-workspace-actions">
            <a className="workbench-action-button" href="/review">
              查看质量复审
            </a>
            <a className="workbench-secondary-link" href="/">
              回到工作台
            </a>
          </div>
        </aside>
      </div>
    </section>
  );
}

function parseBookResponse(payload: unknown): BookResponse | null {
  if (!isRecord(payload) || !isBookPayload(payload.book)) {
    return null;
  }
  return { book: payload.book };
}

function isBookPayload(value: unknown): value is BookPayload {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "number" &&
    typeof value.title === "string" &&
    typeof value.genre === "string" &&
    typeof value.audience === "string" &&
    typeof value.status === "string" &&
    (typeof value.premise === "string" || value.premise === null)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: "草稿",
    canon_locked: "可信设定已锁定",
    producing: "生产中",
    paused: "暂停",
  };
  return labels[status] ?? status;
}
