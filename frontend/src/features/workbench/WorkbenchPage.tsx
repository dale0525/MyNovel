import { useEffect, useState } from "react";

import { getJson } from "@/lib/api";
import type { BookPayload, BooksPayload } from "@/lib/types";

type WorkbenchState =
  | { status: "loading"; books: BookPayload[]; error: null }
  | { status: "ready"; books: BookPayload[]; error: null }
  | { status: "error"; books: BookPayload[]; error: string };

export function WorkbenchPage() {
  const [state, setState] = useState<WorkbenchState>({
    status: "loading",
    books: [],
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    getJson<unknown>("/api/books")
      .then((payload) => {
        const parsed = parseBooksPayload(payload);
        if (!cancelled) {
          if (parsed) {
            setState({ status: "ready", books: parsed.books, error: null });
          } else {
            setState({
              status: "error",
              books: [],
              error: "作品列表格式无效。",
            });
          }
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            books: [],
            error: error instanceof Error ? error.message : "作品列表加载失败。",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="workbench-page" aria-labelledby="workbench-title">
      <div className="workbench-hero">
        <p className="eyebrow">Workbench</p>
        <h1 id="workbench-title">把故事推进到下一步</h1>
        <p className="lede">
          从最近作品继续，或开启新的长篇项目。这里会聚合开书、章节、可信设定和质量检查的下一步动作。
        </p>
      </div>

      {state.status === "loading" && (
        <div className="workbench-panel" role="status">
          正在加载最近作品...
        </div>
      )}

      {state.status === "error" && (
        <div className="workbench-panel workbench-panel--alert" role="alert">
          <h2>作品列表加载失败</h2>
          <p>{state.error}</p>
        </div>
      )}

      {state.status === "ready" && state.books.length === 0 && <EmptyWorkbench />}

      {state.status === "ready" && state.books.length > 0 && (
        <div className="workbench-grid">
          <section className="workbench-panel">
            <div className="workbench-panel__header">
              <div>
                <p className="eyebrow">Recent</p>
                <h2>最近作品</h2>
              </div>
              <a className="workbench-action-button" href={bookHref(state.books[0])}>
                继续推进
              </a>
            </div>
            <ul className="recent-books">
              {state.books.map((book) => (
                <li className="recent-book" key={book.id ?? book.title}>
                  <div>
                    <h3>{book.title}</h3>
                    <p>
                      {book.genre} · {book.audience} · {statusLabel(book.status)}
                    </p>
                  </div>
                  {book.premise && <p>{book.premise}</p>}
                </li>
              ))}
            </ul>
          </section>

          <aside className="workbench-panel workbench-next-action">
            <p className="eyebrow">Next Action</p>
            <h2>从最近作品继续</h2>
            <p>打开最近项目，检查章节状态、可信设定变更和质量建议。</p>
            <a className="workbench-action-button" href={bookHref(state.books[0])}>
              打开最近作品
            </a>
          </aside>
        </div>
      )}
    </section>
  );
}

function EmptyWorkbench() {
  return (
    <div className="workbench-empty">
      <div>
        <p className="eyebrow">No Books</p>
        <h2>还没有作品</h2>
        <p>先从一个清晰的题材、受众和核心承诺开始。创建后，这里会显示最近作品和下一步动作。</p>
      </div>
      <a className="workbench-action-button" href="/books/new">
        开始一本新书
      </a>
    </div>
  );
}

function parseBooksPayload(payload: unknown): BooksPayload | null {
  if (!isRecord(payload) || !Array.isArray(payload.books)) {
    return null;
  }
  if (!payload.books.every(isBookPayload)) {
    return null;
  }
  return { books: payload.books };
}

function isBookPayload(value: unknown): value is BookPayload {
  if (!isRecord(value)) {
    return false;
  }
  return (
    (typeof value.id === "number" || value.id === null) &&
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

function bookHref(book: BookPayload): string {
  return book.id === null ? "/" : `/books/${book.id}`;
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
