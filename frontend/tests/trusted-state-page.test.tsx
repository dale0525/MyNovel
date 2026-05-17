import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { routeForPath } from "@/app/AppRoutes";
import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";
import { TrustedStatePage } from "@/features/canon/TrustedStatePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.pushState(null, "", "/");
});

test("routes book state path to trusted state page", () => {
  const match = routeForPath("/books/42/state");

  expect(match.activePath).toBe("/books/:id/state");
  expect(match.element).toEqual(<BookWorkspacePage bookId={42} view="state" />);
});

test("renders canon section rows without a separate revision preview", async () => {
  window.history.pushState(null, "", "/books/42/state?revisionId=7");
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(trustedStatePayload())));

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument());
  expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  expect(screen.queryByText("Trusted State")).not.toBeInTheDocument();
  expect(screen.queryByText("Revision Request")).not.toBeInTheDocument();
  expect(screen.queryByText("world_rules")).not.toBeInTheDocument();
  expect(screen.queryByText("变化历史")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "世界规则 1 条 已锁定" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "世界规则 1 条 已锁定" }));

  expect(screen.getByText("灯塔会记录航线")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "解锁世界规则" })).toBeInTheDocument();
  expect(screen.queryByText("可修订")).not.toBeInTheDocument();
  expect(screen.queryByText("变更预览")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "应用修改" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "放弃修改" })).not.toBeInTheDocument();
  expect(screen.queryByText("世界规则：已锁定")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "锁定人物" })).not.toBeInTheDocument();
});

test("global revise streams progress, writes canon, and refreshes without revision navigation", async () => {
  window.history.pushState(null, "", "/books/42/state");
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      streamController = controller;
    },
  });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(trustedStatePayload({ selectedRevision: false })))
    .mockResolvedValueOnce(
      new Response(stream, {
        headers: { "Content-Type": "application/x-ndjson; charset=utf-8" },
      }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("全部设定修改意见"), {
    target: { value: "让主角动机和伏笔更清晰" },
  });
  const globalForm = screen.getByLabelText("全部设定修改意见").closest("form")!;
  fireEvent.click(within(globalForm).getByRole("button", { name: "让 AI 修改全部设定" }));
  await waitFor(() => expect(within(globalForm).getByTestId("ai-waiting-indicator")).toHaveTextContent("提交修订中..."));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/canon-proposals/revise-stream",
      expect.objectContaining({
        method: "POST",
        body: "{\"targetSection\":\"characters\",\"instruction\":\"让主角动机和伏笔更清晰\"}",
      }),
    ),
  );

  pushStreamEvent(streamController, { type: "chunk", text: "正在梳理人物动机" });
  await waitFor(() => expect(within(globalForm).getByRole("status")).toHaveTextContent("正在梳理人物动机"));
  pushStreamEvent(streamController, { type: "chunk", text: "检查伏笔关系" });
  pushStreamEvent(streamController, { type: "chunk", text: "准备写入设定" });
  await waitFor(() => expect(within(globalForm).getByRole("status")).toHaveTextContent("检查伏笔关系"));
  expect(within(globalForm).getByRole("status")).toHaveTextContent("准备写入设定");
  expect(within(globalForm).getByRole("status")).not.toHaveTextContent("正在梳理人物动机");
  pushStreamEvent(streamController, {
    type: "done",
    message: "AI 修改已写入设定。",
    state: trustedStatePayload({ selectedRevision: false, characterTrait: "谨慎" }),
  });
  streamController?.close();

  await waitFor(() =>
    expect(within(globalForm).getByRole("status")).toHaveTextContent("AI 修改已写入设定。"),
  );
  expect(fetchMock).not.toHaveBeenCalledWith(
    "/api/books/42/canon-proposals/apply",
    expect.objectContaining({ method: "POST" }),
  );
  expect(window.location.pathname).toBe("/books/42/state");
  expect(window.location.search).toBe("");

  fireEvent.click(screen.getByRole("button", { name: "人物 1 条 待修订" }));
  expect(screen.getByText("谨慎")).toBeInTheDocument();
});

test("canon revise hides pending revision status after hard requirements are met", async () => {
  window.history.pushState(null, "", "/books/42/state");
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(trustedStatePayload({ selectedRevision: false })))
    .mockResolvedValueOnce(
      streamResponse([
        {
          type: "done",
          message: "AI 修改已写入设定。",
          state: trustedStatePayload({ complete: true, selectedRevision: false, characterTrait: "谨慎" }),
        },
      ]),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "人物 1 条 待修订" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("全部设定修改意见"), {
    target: { value: "补齐人物硬性设定" },
  });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修改全部设定" }));

  await waitFor(() => expect(screen.queryByRole("button", { name: /待修订/ })).not.toBeInTheDocument());
  expect(screen.getByRole("button", { name: "人物 1 条 已满足" })).toBeInTheDocument();
});

test("renders animated AI waiting state while canon revise request is pending", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(trustedStatePayload()))
    .mockImplementationOnce(
      () =>
        new Promise<Response>(() => {
          // Keep the revise request pending so the waiting state stays visible.
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "人物 1 条 待修订" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "人物 1 条 待修订" }));
  fireEvent.change(screen.getByLabelText("人物修改意见"), {
    target: { value: "让人物动机更清晰" },
  });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修改人物" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("提交修订中..."));
  expect(screen.getByRole("button", { name: /提交修订中/ })).toBeDisabled();
});

test("running revision renders section-local waiting state without preview actions", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(trustedStatePayload({ revisionStatus: "running" }))),
  );

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "人物 1 条 待修订" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "人物 1 条 待修订" }));

  expect(screen.getByText("修订生成中")).toBeInTheDocument();
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("修订生成中");
  expect(screen.queryByText("变更预览")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "应用修改" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "放弃修改" })).not.toBeInTheDocument();
});

test("failed revision renders section-local failure state without preview actions", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(trustedStatePayload({ revisionStatus: "failed" }))),
  );

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "人物 1 条 待修订" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "人物 1 条 待修订" }));

  await waitFor(() => expect(screen.getByText("修订生成失败")).toBeInTheDocument());
  expect(screen.queryByText("变更预览")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "应用修改" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "放弃修改" })).not.toBeInTheDocument();
});

test("canon proposal action errors render beside the clicked control", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(trustedStatePayload()))
    .mockResolvedValueOnce(
      Response.json(
        {
          error: {
            code: "canon_proposal_action_failed",
            message: "Revision is still running.",
          },
        },
        { status: 400 },
      ),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("全部设定修改意见"), {
    target: { value: "让主角动机更清晰" },
  });
  const globalForm = screen.getByLabelText("全部设定修改意见").closest("form")!;
  fireEvent.click(within(globalForm).getByRole("button", { name: "让 AI 修改全部设定" }));

  await waitFor(() => expect(within(globalForm).getByRole("alert")).toHaveTextContent("修订仍在生成中。"));
  expect(window.location.pathname).toBe("/");
});

test("trusted state expands section rows to submit a section revision", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(trustedStatePayload({ selectedRevision: false })))
    .mockResolvedValueOnce(streamResponse([{ type: "done", state: trustedStatePayload({ selectedRevision: false }) }]));
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "人物 1 条 待修订" }));
  fireEvent.change(screen.getByLabelText("人物修改意见"), {
    target: { value: "让主角动机更清晰" },
  });
  fireEvent.click(screen.getByRole("button", { name: "让 AI 修改人物" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/canon-proposals/revise-stream",
      expect.objectContaining({
        method: "POST",
        body: "{\"targetSection\":\"characters\",\"instruction\":\"让主角动机更清晰\"}",
      }),
    ),
  );
});

test("trusted state section rows can toggle locks", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(trustedStatePayload({ selectedRevision: false })))
    .mockResolvedValueOnce(Response.json(trustedStatePayload({ selectedRevision: false, worldRulesLocked: false })));
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "世界规则 1 条 已锁定" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "世界规则 1 条 已锁定" }));
  fireEvent.click(screen.getByRole("button", { name: "解锁世界规则" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/canon-proposals/lock",
      expect.objectContaining({
        method: "POST",
        body: "{\"section\":\"world_rules\",\"locked\":false}",
      }),
    ),
  );
});

test("trusted state blocks locked sections visually and disables revision submission", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(trustedStatePayload({ selectedRevision: false }))));

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "世界规则 1 条 已锁定" }));

  expect(screen.getByLabelText("世界规则修改意见")).toBeDisabled();
  expect(screen.getByRole("button", { name: "让 AI 修改世界规则" })).toBeDisabled();
});

test("trusted state hides lock actions for sections that still miss hard requirements", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(trustedStatePayload({ selectedRevision: false }))));

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "人物 1 条 待修订" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "锁定人物" })).not.toBeInTheDocument();
});

test("trusted state keeps full section content in expanded rows", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(trustedStatePayload())));

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument());
  expect(screen.queryByText("灯塔会记录航线")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "世界规则 1 条 已锁定" }));

  expect(screen.getByText("灯塔会记录航线")).toBeInTheDocument();
});

test("trusted state keeps section revision intent isolated per row", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(trustedStatePayload({ includeLocations: true, selectedRevision: false }))),
  );

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "人物 1 条 待修订" }));
  fireEvent.change(screen.getByLabelText("人物修改意见"), {
    target: { value: "让人物动机更清晰" },
  });

  expect(screen.getByLabelText("人物修改意见")).toHaveValue("让人物动机更清晰");
  expect(screen.getByRole("button", { name: "让 AI 修改人物" })).toBeEnabled();

  fireEvent.click(screen.getByRole("button", { name: "地点 1 条 已满足" }));

  expect(screen.getByLabelText("人物修改意见")).toHaveValue("让人物动机更清晰");
  expect(screen.getByLabelText("地点修改意见")).toHaveValue("");
  expect(screen.getByRole("button", { name: "让 AI 修改地点" })).toBeDisabled();
});

test("trusted state ignores forced submit for locked revision targets", async () => {
  const fetchMock = vi.fn(async () => Response.json(trustedStatePayload({ selectedRevision: false })));
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "设定" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "世界规则 1 条 已锁定" }));
  fireEvent.submit(screen.getByLabelText("世界规则修改意见").closest("form")!);

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  expect(fetchMock).not.toHaveBeenCalledWith(
    "/api/books/42/canon-proposals/revise-stream",
    expect.objectContaining({ method: "POST" }),
  );
});

function pushStreamEvent(
  controller: ReadableStreamDefaultController<Uint8Array> | null,
  event: Record<string, unknown>,
) {
  if (!controller) {
    throw new Error("Stream controller was not initialized.");
  }
  controller.enqueue(new TextEncoder().encode(`${JSON.stringify(event)}\n`));
}

function streamResponse(events: Array<Record<string, unknown>>): Response {
  return new Response(events.map((event) => JSON.stringify(event)).join("\n"), {
    headers: { "Content-Type": "application/x-ndjson; charset=utf-8" },
  });
}

test("next step blocks incomplete canon and locks complete canon", async () => {
  const incompleteFetch = vi.fn(async () => Response.json(trustedStatePayload({ selectedRevision: false })));
  vi.stubGlobal("fetch", incompleteFetch);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "下一步" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "下一步" }));

  const nextStepRegion = screen.getByRole("region", { name: "下一步" });
  expect(within(nextStepRegion).getByRole("alert")).toHaveTextContent("必须先修正");
  expect(incompleteFetch).not.toHaveBeenCalledWith(
    "/api/books/42/state/lock",
    expect.objectContaining({ method: "POST" }),
  );

  cleanup();
  window.history.pushState(null, "", "/");

  const completeFetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json(trustedStatePayload({ complete: true, selectedRevision: false })))
    .mockResolvedValueOnce(Response.json({ redirectTo: "/books/42" }));
  vi.stubGlobal("fetch", completeFetch);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "下一步" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "下一步" }));

  await waitFor(() =>
    expect(completeFetch).toHaveBeenCalledWith(
      "/api/books/42/state/lock",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(window.location.pathname).toBe("/books/42");
});

function trustedStatePayload({
  revisionStatus = "pending",
  selectedRevision = true,
  includeLocations = false,
  complete = false,
  worldRulesLocked = true,
  characterTrait,
}: {
  revisionStatus?: string;
  selectedRevision?: boolean;
  includeLocations?: boolean;
  complete?: boolean;
  worldRulesLocked?: boolean;
  characterTrait?: string;
} = {}) {
  const character = characterTrait ? { name: "岑星", trait: characterTrait } : { name: "岑星" };
  const revision = {
    id: 7,
    bookId: 42,
    baseCanonVersion: 2,
    targetSection: "characters",
    instruction: "让主角更谨慎",
    allowedSections: ["characters"],
    lockedSections: ["world_rules"],
    changedSections: { characters: [{ name: "岑星", trait: "谨慎" }] },
    blockedSections: [{ section: "world_rules", reason: "已锁定" }],
    summary: "补强人物风险意识。",
    risks: [],
    status: revisionStatus,
    createdAt: "2026-05-16T00:00:00+00:00",
    appliedAt: null,
  };

  return {
    book: {
      id: 42,
      title: "星港遗梦",
      genre: "科幻",
      audience: "成人",
      status: "draft",
      premise: "领航员追查失落星港的真相。",
    },
    latestCanon: {
      id: 3,
      bookId: 42,
      version: 2,
      content: {
        world_rules: [{ rule: "灯塔会记录航线" }],
        characters: [character],
        state_history: [],
        locations: [{ name: "白塔港" }],
      },
      createdAt: "2026-05-16T00:00:00+00:00",
    },
    canonSections: [
      {
        key: "world_rules",
        anchor: "world",
        label: "世界规则",
        editable: true,
        locked: worldRulesLocked,
        content: [{ rule: "灯塔会记录航线" }],
      },
      {
        key: "characters",
        anchor: "characters",
        label: "人物",
        editable: true,
        locked: false,
        content: [character],
      },
      {
        key: "state_history",
        anchor: "state-history",
        label: "变化历史",
        editable: false,
        locked: true,
        content: [],
      },
      ...(includeLocations
        ? [
            {
              key: "locations",
              anchor: "locations",
              label: "地点",
              editable: true,
              locked: false,
              content: [{ name: "白塔港" }],
            },
          ]
        : []),
    ],
    sectionLocks: {
      world_rules: worldRulesLocked,
      characters: false,
      locations: false,
      state_history: true,
    },
    readiness: complete
      ? { complete: true, missingSections: [], messages: [] }
      : { complete: false, missingSections: ["characters"], messages: ["人物至少 3 条"] },
    pendingRevisions: selectedRevision ? [revision] : [],
    selectedRevision: selectedRevision ? revision : null,
  };
}
