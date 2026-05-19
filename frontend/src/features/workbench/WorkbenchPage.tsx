import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, FilePlus2, FolderOpen, PenLine } from "lucide-react";

import { getJson } from "@/lib/api";
import type { BookPayload, BooksPayload, OpenBookBlueprintSummaryPayload } from "@/lib/types";

type WorkbenchState =
  | { status: "loading"; books: BookPayload[]; blueprints: OpenBookBlueprintSummaryPayload[]; error: null }
  | { status: "ready"; books: BookPayload[]; blueprints: OpenBookBlueprintSummaryPayload[]; error: null }
  | { status: "error"; books: BookPayload[]; blueprints: OpenBookBlueprintSummaryPayload[]; error: string };

export function WorkbenchPage() {
  const [state, setState] = useState<WorkbenchState>({
    status: "loading",
    books: [],
    blueprints: [],
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    getJson<unknown>("/api/books")
      .then((payload) => {
        const parsed = parseBooksPayload(payload);
        if (!cancelled) {
          if (parsed) {
            setState({ status: "ready", books: parsed.books, blueprints: parsed.blueprints, error: null });
          } else {
            setState({
              status: "error",
              books: [],
              blueprints: [],
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
            blueprints: [],
            error: error instanceof Error ? error.message : "作品列表加载失败。",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="workbench-page workbench-page--home" aria-labelledby="workbench-title">
      <div className="workbench-hero">
        <div>
          <p className="eyebrow">工作台</p>
          <h1 id="workbench-title">把故事推进到下一步</h1>
          <p className="lede">
            从最近作品继续，或开启新的长篇项目。这里会聚合开书、章节、可信设定和质量检查的下一步动作。
          </p>
        </div>
        <div className="workbench-hero__actions" aria-label="工作台快捷入口">
          <a className="workbench-quick-action" href="/books/new">
            <FilePlus2 aria-hidden="true" size={18} />
            新开一本书
          </a>
          <a className="workbench-quick-action" href="/books/import">
            <FolderOpen aria-hidden="true" size={18} />
            导入项目
          </a>
        </div>
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

      {state.status === "ready" && state.books.length === 0 && state.blueprints.length === 0 && <EmptyWorkbench />}

      {state.status === "ready" && state.blueprints.length > 0 && (
        <OpenBookBlueprintPanel blueprints={state.blueprints} />
      )}

      {state.status === "ready" && state.books.length > 0 && (
        <div className="workbench-grid">
          <section className="workbench-panel workbench-project-panel">
            <div className="workbench-panel__header">
              <div>
                <p className="eyebrow">项目</p>
                <h2>选择继续哪个项目</h2>
              </div>
              <a className="workbench-action-button" href={bookHref(state.books[0])}>
                继续推进
              </a>
            </div>
            <ul className="recent-books">
              {state.books.map((book) => (
                <li key={book.id ?? book.title}>
                  <a
                    aria-label={`继续《${book.title}》`}
                    className="recent-book recent-book--link"
                    href={bookHref(book)}
                  >
                    <span className="recent-book__icon" aria-hidden="true">
                      <BookOpen size={18} />
                    </span>
                    <span className="recent-book__body">
                      <h3>{book.title}</h3>
                      <p>
                        {book.genre} · {book.audience} · {statusLabel(book.status)}
                      </p>
                      {book.premise && <small>{book.premise}</small>}
                    </span>
                    <span className="recent-book__status">
                      <PenLine aria-hidden="true" size={15} />
                      继续
                    </span>
                    <ArrowRight aria-hidden="true" size={18} />
                  </a>
                </li>
              ))}
            </ul>
          </section>

          <aside className="workbench-panel workbench-next-action">
            <p className="eyebrow">下一步</p>
            <h2>从最近作品继续</h2>
            <p>打开最近项目，检查卷纲、可信设定变更和质量建议。</p>
            <a className="workbench-action-button" href={bookHref(state.books[0])}>
              打开最近作品
            </a>
            <div className="workbench-next-action__list" aria-label="最近项目快捷入口">
              {state.books.slice(0, 3).map((book) => (
                <a href={bookHref(book)} key={book.id ?? book.title}>
                  <span>{book.title}</span>
                  <strong>{statusLabel(book.status)}</strong>
                </a>
              ))}
            </div>
          </aside>
        </div>
      )}
    </section>
  );
}

function OpenBookBlueprintPanel({ blueprints }: { blueprints: OpenBookBlueprintSummaryPayload[] }) {
  return (
    <section className="workbench-panel workbench-project-panel">
      <div className="workbench-panel__header">
        <div>
          <p className="eyebrow">开书阶段</p>
          <h2>继续开书</h2>
        </div>
        <a className="workbench-action-button" href={`/blueprints/${blueprints[0].id}`}>
          继续最近蓝图
        </a>
      </div>
      <ul className="recent-books">
        {blueprints.map((blueprint) => (
          <li key={blueprint.id}>
            <a
              aria-label={`继续开书《${blueprint.title}》`}
              className="recent-book recent-book--link"
              href={`/blueprints/${blueprint.id}`}
            >
              <span className="recent-book__icon" aria-hidden="true">
                <FilePlus2 size={18} />
              </span>
              <span className="recent-book__body">
                <h3>{blueprint.title}</h3>
                <p>
                  {blueprintStatusLabel(blueprint.status)} · 第 {blueprint.version} 版
                </p>
                <small>{blueprint.instruction || blueprint.idea}</small>
              </span>
              <span className="recent-book__status">
                <PenLine aria-hidden="true" size={15} />
                继续
              </span>
              <ArrowRight aria-hidden="true" size={18} />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

function EmptyWorkbench() {
  return (
    <div className="workbench-empty">
      <div>
        <p className="eyebrow">暂无作品</p>
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
  const blueprints = payload.blueprints;
  if (blueprints !== undefined && !Array.isArray(blueprints)) {
    return null;
  }
  if (Array.isArray(blueprints) && !blueprints.every(isBlueprintSummaryPayload)) {
    return null;
  }
  return { books: payload.books, blueprints: Array.isArray(blueprints) ? blueprints : [] };
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

function isBlueprintSummaryPayload(value: unknown): value is OpenBookBlueprintSummaryPayload {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.id === "number" &&
    (typeof value.parentId === "number" || value.parentId === null) &&
    typeof value.version === "number" &&
    typeof value.status === "string" &&
    typeof value.title === "string" &&
    typeof value.idea === "string" &&
    (typeof value.instruction === "string" || value.instruction === null) &&
    (typeof value.createdAt === "string" || value.createdAt === null)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function bookHref(book: BookPayload): string {
  return book.id === null ? "/" : `/books/${book.id}`;
}

function blueprintStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "蓝图排队中",
    running: "蓝图生成中",
    succeeded: "蓝图已生成",
    failed: "蓝图生成失败",
  };
  return labels[status] ?? "蓝图处理中";
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: "草稿",
    canon_locked: "可信设定已锁定",
    producing: "生产中",
    paused: "暂停",
  };
  return labels[status] ?? "未知状态";
}
