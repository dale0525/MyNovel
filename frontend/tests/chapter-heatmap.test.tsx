import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("chapter heatmap click focuses the matching volume and selects the batch target", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(multiVolumeBookPayload())));

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument());
  expect(screen.getByRole("button", { name: /第一卷 · 星港卷/ })).toHaveAttribute("aria-pressed", "true");

  const secondChapterCell = screen.getByRole("button", { name: /第 11 章 · 深空裂缝/ });
  fireEvent.click(secondChapterCell);

  expect(screen.getByRole("button", { name: /第一卷 · 星港卷/ })).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByRole("button", { name: /第二卷 · 深空卷/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("选择第 11 章 · 深空裂缝")).toBeChecked();
  expect(secondChapterCell).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "生成选中的 1 章" })).toBeInTheDocument();
});

test("clicking a selected heatmap cell again clears that batch target", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(multiVolumeBookPayload())));

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument());
  const secondChapterCell = screen.getByRole("button", { name: /第 11 章 · 深空裂缝/ });

  fireEvent.click(secondChapterCell);
  expect(secondChapterCell).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("选择第 11 章 · 深空裂缝")).toBeChecked();

  fireEvent.click(secondChapterCell);

  expect(secondChapterCell).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByLabelText("选择第 11 章 · 深空裂缝")).not.toBeChecked();
  expect(screen.getByRole("button", { name: "选择章节后生成" })).toBeDisabled();
});

test("dragging across chapter heatmap selects multiple batch targets", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(multiVolumeBookPayload())));

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument());
  const firstChapterCell = screen.getByRole("button", { name: /第 1 章 · 失落灯塔/ });
  const secondChapterCell = screen.getByRole("button", { name: /第 11 章 · 深空裂缝/ });

  fireEvent.mouseDown(firstChapterCell);
  fireEvent.mouseEnter(secondChapterCell, { buttons: 1 });
  fireEvent.mouseUp(secondChapterCell);

  expect(firstChapterCell).toHaveAttribute("aria-pressed", "true");
  expect(secondChapterCell).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "生成选中的 2 章" })).toBeInTheDocument();
});

test("dragging from selected heatmap cells clears multiple batch targets", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(multiVolumeBookPayload())));

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument());
  const firstChapterCell = screen.getByRole("button", { name: /第 1 章 · 失落灯塔/ });
  const secondChapterCell = screen.getByRole("button", { name: /第 11 章 · 深空裂缝/ });

  fireEvent.mouseDown(firstChapterCell);
  fireEvent.mouseEnter(secondChapterCell, { buttons: 1 });
  fireEvent.mouseUp(secondChapterCell);
  expect(screen.getByRole("button", { name: "生成选中的 2 章" })).toBeInTheDocument();

  fireEvent.mouseDown(secondChapterCell);
  fireEvent.mouseEnter(firstChapterCell, { buttons: 1 });
  fireEvent.mouseUp(firstChapterCell);

  expect(firstChapterCell).toHaveAttribute("aria-pressed", "false");
  expect(secondChapterCell).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByLabelText("选择第 1 章 · 失落灯塔")).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: /第二卷 · 深空卷/ }));
  expect(screen.getByLabelText("选择第 11 章 · 深空裂缝")).not.toBeChecked();
  expect(screen.getByRole("button", { name: "选择章节后生成" })).toBeDisabled();
});

test("lower volume and chapter checkboxes keep heatmap cells selected", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(multiVolumeBookPayload())));

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument());
  const firstChapterCell = screen.getByRole("button", { name: /第 1 章 · 失落灯塔/ });
  const secondChapterCell = screen.getByRole("button", { name: /第 11 章 · 深空裂缝/ });

  fireEvent.click(screen.getByLabelText("选择第一卷 · 星港卷"));
  expect(firstChapterCell).toHaveAttribute("aria-pressed", "true");

  fireEvent.click(screen.getByRole("button", { name: /第二卷 · 深空卷/ }));
  fireEvent.click(screen.getByLabelText("选择第 11 章 · 深空裂缝"));

  expect(secondChapterCell).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "生成选中的 2 章" })).toBeInTheDocument();
});

test("hovering a heatmap cell shows chapter overview details", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(multiVolumeBookPayload())));

  render(<BookWorkspacePage bookId={42} view="chapters" />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "章节" })).toBeInTheDocument());
  const secondChapterCell = screen.getByRole("button", { name: /第 11 章 · 深空裂缝/ });

  fireEvent.mouseEnter(secondChapterCell);

  const tooltip = screen.getByRole("tooltip");
  expect(tooltip).toHaveTextContent("第二卷 · 深空卷");
  expect(tooltip).toHaveTextContent("星港裂缝撕开第一条航线。");
  expect(tooltip).toHaveTextContent("待生产");

  fireEvent.mouseLeave(secondChapterCell);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});

function multiVolumeBookPayload() {
  return {
    book: {
      id: 42,
      title: "星港遗梦",
      genre: "科幻",
      audience: "成人",
      status: "canon_locked",
      premise: "领航员追查失落星港的真相。",
    },
    wordTargets: {
      targetWordCount: 5600,
      chapterWordCount: 2800,
    },
    chapters: [
      {
        id: 8,
        bookId: 42,
        number: 1,
        title: "失落灯塔",
        status: "planned",
        summary: "领航员发现星港残影。",
        wordCount: 0,
        reviewerNote: null,
        updatedAt: "2026-05-16T00:00:00+00:00",
        volumeNumber: 1,
      },
      {
        id: 9,
        bookId: 42,
        number: 11,
        title: "深空裂缝",
        status: "planned",
        summary: "星港裂缝撕开第一条航线。",
        wordCount: 0,
        reviewerNote: null,
        updatedAt: "2026-05-16T00:00:00+00:00",
        volumeNumber: 2,
      },
    ],
    latestCanon: {
      id: 3,
      bookId: 42,
      version: 2,
      content: {
        world_rules: [{ rule: "灯塔会记录航线" }],
      },
      createdAt: "2026-05-16T00:00:00+00:00",
    },
    runTraces: [],
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
      {
        id: 3,
        bookId: 42,
        volumeNumber: 2,
        title: "深空卷",
        coreConflict: "星港裂缝开始吞没航线。",
        pacingCurve: ["扩张", "反转"],
        payoffDistribution: ["裂缝来源"],
        keyTurns: ["发现裂缝", "失去坐标"],
        commitments: ["保持星港谜题主线"],
      },
    ],
  };
}
