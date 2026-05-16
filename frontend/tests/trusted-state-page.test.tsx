import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { routeForPath } from "@/app/AppRoutes";
import { TrustedStatePage } from "@/features/canon/TrustedStatePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.pushState(null, "", "/");
});

test("routes book state path to trusted state page", () => {
  const match = routeForPath("/books/42/state");

  expect(match.activePath).toBe("/books/:id/state");
  expect(match.element).toEqual(<TrustedStatePage bookId={42} />);
});

test("renders canon sections locks revision changes and blocked sections", async () => {
  window.history.pushState(null, "", "/books/42/state?revisionId=7");
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(trustedStatePayload())));

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "可信设定" })).toBeInTheDocument());
  expect(screen.getByText("世界规则")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "完整设定内容" }));
  expect(screen.getByText("灯塔会记录航线")).toBeInTheDocument();
  expect(screen.getAllByText("人物")).toHaveLength(2);
  expect(screen.getAllByText("可修订")[0]).toBeInTheDocument();
  expect(screen.getByText("变更预览")).toBeInTheDocument();
  expect(screen.getByText("岑星")).toBeInTheDocument();
  expect(screen.getAllByText("已锁定")[0]).toBeInTheDocument();
  expect(screen.getByText("world_rules: 已锁定")).toBeInTheDocument();
});

test("apply discard and revise actions call canon proposal endpoints", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(trustedStatePayload()))
    .mockResolvedValueOnce(Response.json({ revision: { ...trustedStatePayload().selectedRevision, status: "applied" } }))
    .mockResolvedValueOnce(Response.json({ revision: { ...trustedStatePayload().selectedRevision, status: "discarded" } }))
    .mockResolvedValueOnce(Response.json({ revisionId: 9, redirectTo: "/books/42/state?revisionId=9" }, { status: 202 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("button", { name: "应用修订" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "应用修订" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/canon-proposals/apply",
      expect.objectContaining({ method: "POST" }),
    ),
  );

  fireEvent.click(screen.getByRole("button", { name: "放弃修订" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/canon-proposals/discard",
      expect.objectContaining({ method: "POST" }),
    ),
  );

  fireEvent.click(screen.getByRole("button", { name: /人物/ }));
  fireEvent.change(screen.getByLabelText("修订意图"), {
    target: { value: "让人物动机更清晰" },
  });
  fireEvent.click(screen.getByRole("button", { name: "生成修订预览" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/canon-proposals/revise",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(window.location.pathname).toBe("/books/42/state");
  expect(window.location.search).toBe("?revisionId=9");
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

  await waitFor(() => expect(screen.getByRole("button", { name: "生成修订预览" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /人物/ }));
  fireEvent.change(screen.getByLabelText("修订意图"), {
    target: { value: "让人物动机更清晰" },
  });
  fireEvent.click(screen.getByRole("button", { name: "生成修订预览" }));

  await waitFor(() => expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("提交修订中..."));
  expect(screen.getByRole("button", { name: /提交修订中/ })).toBeDisabled();
});

test("running revision hides apply actions until preview is pending", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(trustedStatePayload({ revisionStatus: "running" }))),
  );

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByText("修订生成中")).toBeInTheDocument());
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("修订生成中");
  expect(screen.queryByRole("button", { name: "应用修订" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "放弃修订" })).not.toBeInTheDocument();
});

test("failed revision hides apply actions and shows failure state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(trustedStatePayload({ revisionStatus: "failed" }))),
  );

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByText("修订生成失败")).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "应用修订" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "放弃修订" })).not.toBeInTheDocument();
});

test("canon proposal action errors render feedback and keep user on the page", async () => {
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

  await waitFor(() => expect(screen.getByRole("button", { name: "应用修订" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "应用修订" }));

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Revision is still running."));
  expect(window.location.pathname).toBe("/");
});

test("trusted state uses a section map to select the revision target", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(Response.json(trustedStatePayload({ selectedRevision: false })))
    .mockResolvedValueOnce(Response.json({ revisionId: 9, redirectTo: "/books/42/state?revisionId=9" }, { status: 202 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "可信设定" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /人物/ }));
  fireEvent.change(screen.getByLabelText("修订意图"), {
    target: { value: "让主角动机更清晰" },
  });
  fireEvent.click(screen.getByRole("button", { name: "生成修订预览" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/books/42/canon-proposals/revise",
      expect.objectContaining({
        method: "POST",
        body: "{\"targetSection\":\"characters\",\"instruction\":\"让主角动机更清晰\"}",
      }),
    ),
  );
});

test("trusted state blocks locked sections visually and disables revision submission", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(trustedStatePayload({ selectedRevision: false }))));

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "可信设定" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /世界规则/ }));

  expect(screen.getByLabelText("修订意图")).toBeDisabled();
  expect(screen.getByRole("button", { name: "生成修订预览" })).toBeDisabled();
  expect(screen.getByRole("region", { name: "影响预览" })).toHaveTextContent("已锁定");
});

test("trusted state hides apply until a pending revision preview exists", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(trustedStatePayload({ selectedRevision: false }))));

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "可信设定" })).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "应用修订" })).not.toBeInTheDocument();
});

test("trusted state keeps full section content in an advanced disclosure", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(trustedStatePayload())));

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "可信设定" })).toBeInTheDocument());
  expect(screen.queryByText("灯塔会记录航线")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "完整设定内容" }));

  expect(screen.getByText("灯塔会记录航线")).toBeInTheDocument();
});

test("trusted state clears revision intent when switching editable sections", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json(trustedStatePayload({ includeLocations: true, selectedRevision: false }))),
  );

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "可信设定" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /人物/ }));
  fireEvent.change(screen.getByLabelText("修订意图"), {
    target: { value: "让人物动机更清晰" },
  });

  expect(screen.getByLabelText("修订意图")).toHaveValue("让人物动机更清晰");
  expect(screen.getByRole("button", { name: "生成修订预览" })).toBeEnabled();

  fireEvent.click(screen.getByRole("button", { name: /地点/ }));

  expect(screen.getByText("当前分区：地点")).toBeInTheDocument();
  expect(screen.getByLabelText("修订意图")).toHaveValue("");
  expect(screen.getByRole("button", { name: "生成修订预览" })).toBeDisabled();
});

test("trusted state ignores forced submit for locked revision targets", async () => {
  const fetchMock = vi.fn(async () => Response.json(trustedStatePayload({ selectedRevision: false })));
  vi.stubGlobal("fetch", fetchMock);

  render(<TrustedStatePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "可信设定" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /世界规则/ }));
  fireEvent.submit(screen.getByLabelText("修订意图").closest("form")!);

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  expect(fetchMock).not.toHaveBeenCalledWith(
    "/api/books/42/canon-proposals/revise",
    expect.objectContaining({ method: "POST" }),
  );
});

function trustedStatePayload({
  revisionStatus = "pending",
  selectedRevision = true,
  includeLocations = false,
}: {
  revisionStatus?: string;
  selectedRevision?: boolean;
  includeLocations?: boolean;
} = {}) {
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
        characters: [{ name: "岑星" }],
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
        locked: true,
        content: [{ rule: "灯塔会记录航线" }],
      },
      {
        key: "characters",
        anchor: "characters",
        label: "人物",
        editable: true,
        locked: false,
        content: [{ name: "岑星" }],
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
      world_rules: true,
      characters: false,
      locations: false,
      state_history: true,
    },
    readiness: { complete: false, missingSections: ["characters"], messages: ["人物至少 3 条"] },
    pendingRevisions: selectedRevision ? [revision] : [],
    selectedRevision: selectedRevision ? revision : null,
  };
}
