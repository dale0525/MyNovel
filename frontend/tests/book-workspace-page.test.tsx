import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("renders book workspace details", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        book: {
          id: 42,
          title: "星港遗梦",
          genre: "科幻",
          audience: "成人",
          status: "draft",
          premise: "领航员追查失落星港的真相。",
        },
        chapters: [
          {
            id: 8,
            bookId: 42,
            number: 1,
            title: "失落灯塔",
            status: "running",
            summary: "领航员发现星港残影。",
            wordCount: 1200,
            reviewerNote: null,
            updatedAt: "2026-05-16T00:00:00+00:00",
          },
        ],
        latestCanon: {
          id: 3,
          bookId: 42,
          version: 2,
          content: {
            world_rules: [{ rule: "灯塔会记录航线" }],
            characters: [{ name: "岑星" }],
            chapter_summaries: [],
          },
          createdAt: "2026-05-16T00:00:00+00:00",
        },
        runTraces: [
          {
            id: 5,
            bookId: 42,
            stage: "chapter_draft",
            promptId: "chapter_draft",
            promptVersion: "1",
            model: "gpt-test",
            cost: { tokens: 1200 },
            metadata: { chapter: 1 },
            createdAt: "2026-05-16T00:00:00+00:00",
          },
        ],
        volumePlans: [
          {
            id: 2,
            bookId: 42,
            volumeNumber: 1,
            title: "星港卷",
            coreConflict: "寻找失落星港。",
            pacingCurve: ["悬疑", "突破"],
            payoffDistribution: ["灯塔真相"],
            keyTurns: ["发现灯塔", "进入星港"],
            commitments: ["不背离星港谜题"],
          },
        ],
      }),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("科幻 · 成人 · 草稿")).toBeInTheDocument();
  expect(screen.getByText("领航员追查失落星港的真相。")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "当前任务" })).toBeInTheDocument();
  expect(screen.getAllByText("第 1 章 · 失落灯塔")).toHaveLength(2);
  expect(screen.getByRole("heading", { name: "章节队列" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "可信设定摘要" })).toBeInTheDocument();
  expect(screen.getByText("灯塔会记录航线")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "最近 AI 进度" })).toBeInTheDocument();
  expect(screen.getByText("chapter_draft")).toBeInTheDocument();
});

test("does not treat accepted chapters as the current task", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        book: {
          id: 42,
          title: "星港遗梦",
          genre: "科幻",
          audience: "成人",
          status: "draft",
          premise: "领航员追查失落星港的真相。",
        },
        chapters: [
          {
            id: 8,
            bookId: 42,
            number: 1,
            title: "已完成灯塔",
            status: "accepted",
            summary: "这一章已经接受。",
            wordCount: 1200,
            reviewerNote: null,
            updatedAt: "2026-05-16T00:00:00+00:00",
          },
        ],
        latestCanon: null,
        runTraces: [],
        volumePlans: [],
      }),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("暂无待推进章节。可以先检查可信设定，再创建章节生产任务。")).toBeInTheDocument();
  expect(screen.getByText("已接受 · 1200 字")).toBeInTheDocument();
});

test("aborts in-flight book fetch on unmount", () => {
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      signal = init?.signal ?? undefined;
      return new Promise<Response>(() => {});
    }),
  );

  const { unmount } = render(<BookWorkspacePage bookId={42} />);

  expect(signal?.aborted).toBe(false);
  unmount();
  expect(signal?.aborted).toBe(true);
});
