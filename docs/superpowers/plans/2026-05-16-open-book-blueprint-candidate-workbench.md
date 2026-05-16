# Open Book Blueprint Candidate Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the open-book blueprint page into a candidate comparison and decision workbench that shows the full LLM blueprint without overwhelming authors.

**Architecture:** Add a focused TypeScript normalization helper for candidate data, then refactor `BlueprintPage` to render candidate tabs, a comparison table, candidate details, a decision panel, directed revision context, and an accept preview. Keep API compatibility by sending the existing `selectedTitle` and `revisionNotes` fields while adding optional candidate context that the backend can ignore for now.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, CSS in `globals.css`, existing MyNovel JSON API.

---

## File Map

- Create `frontend/src/features/open-book/blueprintCandidates.ts`
  - Owns all data-shaping logic for blueprint candidates.
  - Exports `BlueprintCandidateView`, `normalizeBlueprintCandidates`, and small formatting helpers for UI use.
- Modify `frontend/src/features/open-book/BlueprintPage.tsx`
  - Owns fetching, polling, action submission, candidate selection state, and page composition.
  - Uses helper output instead of reading raw `content` directly inside JSX.
- Modify `frontend/src/styles/globals.css`
  - Adds scoped `.blueprint-*` styles for candidate tabs, comparison table, detail modules, timeline, and decision panel.
- Modify `frontend/tests/blueprint-page.test.tsx`
  - Covers candidate switching, comparison, detail rendering, old blueprint fallback, accept body, directed revision body, and pending duplicate protection.
- Create `frontend/tests/blueprint-candidates.test.ts`
  - Covers candidate normalization independent of React rendering.

Keep `BlueprintPage.tsx` below 1000 lines. If the implementation approaches 800 lines, split presentational pieces into `frontend/src/features/open-book/BlueprintCandidateWorkbench.tsx` before continuing.

## Verification Commands

Use pixi-managed tools:

```bash
pixi run npm --prefix frontend test -- blueprint-candidates.test.ts
pixi run npm --prefix frontend test -- blueprint-page.test.tsx
pixi run npm --prefix frontend run typecheck
pixi run npm --prefix frontend run build
```

---

### Task 1: Candidate Normalization Helper

**Files:**
- Create: `frontend/src/features/open-book/blueprintCandidates.ts`
- Create: `frontend/tests/blueprint-candidates.test.ts`

- [ ] **Step 1: Write failing normalization tests**

Create `frontend/tests/blueprint-candidates.test.ts`:

```ts
import { describe, expect, test } from "vitest";

import { normalizeBlueprintCandidates } from "@/features/open-book/blueprintCandidates";

describe("normalizeBlueprintCandidates", () => {
  test("merges candidate-specific fields over global blueprint fields", () => {
    const candidates = normalizeBlueprintCandidates({
      title_options: ["长夜档案", "禁书回声"],
      genre: "奇幻",
      audience: "成人类型小说读者",
      selling_points: ["禁书悬疑"],
      reader_promises: ["真相反转"],
      protagonist: { name: "林既明", identity: "档案员" },
      world: { summary: "禁书会吞噬记忆" },
      central_conflict: "档案员追查禁书真相。",
      chapter_directions: [{ title: "第1章", goal: "发现禁书" }],
      candidates: [
        {
          title: "长夜档案",
          genre: "都市奇幻",
          central_conflict: "档案员用禁书交易找回失踪同事。",
          selling_points: ["禁书代价", "记忆悬疑"],
        },
        {
          title: "禁书回声",
          audience: "悬疑推理读者",
          protagonist: { name: "沈回声", role: "修复师" },
          chapter_directions: [
            { title: "回声", goal: "听见第一本禁书里的求救声" },
            { title: "借阅证", goal: "发现借阅记录被篡改" },
          ],
        },
      ],
    });

    expect(candidates).toHaveLength(2);
    expect(candidates[0]).toMatchObject({
      index: 0,
      title: "长夜档案",
      genre: "都市奇幻",
      audience: "成人类型小说读者",
      centralConflict: "档案员用禁书交易找回失踪同事。",
      sellingPoints: ["禁书代价", "记忆悬疑"],
      readerPromises: ["真相反转"],
    });
    expect(candidates[1]).toMatchObject({
      index: 1,
      title: "禁书回声",
      genre: "奇幻",
      audience: "悬疑推理读者",
      protagonist: { name: "沈回声", role: "修复师" },
    });
    expect(candidates[1].chapterDirections[0]).toEqual({
      number: 1,
      title: "回声",
      goal: "听见第一本禁书里的求救声",
    });
  });

  test("wraps old global-only content as one default candidate", () => {
    const candidates = normalizeBlueprintCandidates({
      title_options: ["长夜档案"],
      genre: "奇幻",
      audience: "成人",
      selling_points: ["禁书悬疑"],
      reader_promises: ["真相反转"],
      protagonist: "失意档案员",
      world: "禁书会吞噬记忆",
      central_conflict: "档案员追查禁书真相。",
      chapter_directions: ["发现禁书"],
    });

    expect(candidates).toHaveLength(1);
    expect(candidates[0]).toMatchObject({
      index: 0,
      title: "长夜档案",
      genre: "奇幻",
      audience: "成人",
      protagonist: "失意档案员",
      world: "禁书会吞噬记忆",
      centralConflict: "档案员追查禁书真相。",
    });
    expect(candidates[0].chapterDirections).toEqual([
      { number: 1, title: "第 01 章", goal: "发现禁书" },
    ]);
  });

  test("keeps unknown fields in extras for progressive disclosure", () => {
    const candidates = normalizeBlueprintCandidates({
      title_options: ["长夜档案"],
      genre: "奇幻",
      secret_sauce: "章节末尾都用禁书代价做钩子",
      candidates: [{ title: "长夜档案", market_angle: "悬疑向强钩子" }],
    });

    expect(candidates[0].extras).toEqual({
      market_angle: "悬疑向强钩子",
      secret_sauce: "章节末尾都用禁书代价做钩子",
    });
  });
});
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pixi run npm --prefix frontend test -- blueprint-candidates.test.ts
```

Expected: FAIL because `@/features/open-book/blueprintCandidates` does not exist.

- [ ] **Step 3: Implement normalization helper**

Create `frontend/src/features/open-book/blueprintCandidates.ts`:

```ts
const candidateTitleKeys = ["title", "selected_title", "title_option", "book_title"] as const;

const knownContentKeys = new Set([
  "title_options",
  "candidates",
  "genre",
  "audience",
  "selling_points",
  "reader_promises",
  "protagonist",
  "world",
  "central_conflict",
  "premise",
  "chapter_directions",
  "selected_title",
]);

export type ChapterDirectionView = {
  number: number;
  title: string;
  goal: string;
};

export type BlueprintCandidateView = {
  index: number;
  title: string;
  genre: string;
  audience: string;
  sellingPoints: string[];
  readerPromises: string[];
  protagonist: unknown;
  world: unknown;
  centralConflict: string;
  chapterDirections: ChapterDirectionView[];
  extras: Record<string, unknown>;
};

export function normalizeBlueprintCandidates(content: Record<string, unknown>): BlueprintCandidateView[] {
  const titles = titleOptions(content);
  if (titles.length === 0) {
    return [];
  }

  const rawCandidates = Array.isArray(content.candidates) ? content.candidates : [];
  return titles.map((title, index) => {
    const rawCandidate = candidateForTitle(rawCandidates, title, index);
    const merged = { ...content, ...rawCandidate, title_options: [title], selected_title: title };
    return candidateFromMergedContent(merged, title, index);
  });
}

export function textValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function listValues(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item).trim()).filter(Boolean);
}

export function summaryValue(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (Array.isArray(value)) {
    return value.map((item) => summaryValue(item)).filter(Boolean).join("、");
  }
  if (isRecord(value)) {
    const preferred = ["summary", "name", "identity", "role", "goal", "flaw", "rules"];
    return preferred
      .map((key) => summaryValue(value[key]))
      .filter(Boolean)
      .slice(0, 3)
      .join(" / ");
  }
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}

export function fieldEntries(value: unknown): Array<[string, string]> {
  if (!isRecord(value)) {
    return [];
  }
  const preferred = ["name", "identity", "role", "goal", "flaw", "summary", "rules"];
  const orderedKeys = [
    ...preferred.filter((key) => key in value),
    ...Object.keys(value).filter((key) => !preferred.includes(key)),
  ];
  return orderedKeys
    .map((key): [string, string] => [key, summaryValue(value[key])])
    .filter((entry) => entry[1].length > 0);
}

function candidateFromMergedContent(
  merged: Record<string, unknown>,
  title: string,
  index: number,
): BlueprintCandidateView {
  return {
    index,
    title,
    genre: textValue(merged.genre),
    audience: textValue(merged.audience),
    sellingPoints: listValues(merged.selling_points),
    readerPromises: listValues(merged.reader_promises),
    protagonist: merged.protagonist ?? "",
    world: merged.world ?? "",
    centralConflict: textValue(merged.central_conflict) || textValue(merged.premise),
    chapterDirections: chapterDirections(merged.chapter_directions),
    extras: extrasFromContent(merged),
  };
}

function titleOptions(content: Record<string, unknown>): string[] {
  if (!Array.isArray(content.title_options)) {
    return [];
  }
  return content.title_options.map((item) => String(item).trim()).filter(Boolean);
}

function candidateForTitle(candidates: unknown[], title: string, index: number): Record<string, unknown> {
  for (const candidate of candidates) {
    if (isRecord(candidate) && candidateTitle(candidate) === title) {
      return candidate;
    }
  }
  const byIndex = candidates[index];
  return isRecord(byIndex) ? byIndex : {};
}

function candidateTitle(candidate: Record<string, unknown>): string {
  for (const key of candidateTitleKeys) {
    const title = textValue(candidate[key]);
    if (title) {
      return title;
    }
  }
  return "";
}

function chapterDirections(value: unknown): ChapterDirectionView[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item, index) => chapterDirection(index + 1, item));
}

function chapterDirection(number: number, value: unknown): ChapterDirectionView {
  const fallbackTitle = `第 ${String(number).padStart(2, "0")} 章`;
  if (isRecord(value)) {
    const title = textValue(value.title) || textValue(value.chapter) || fallbackTitle;
    const goal = textValue(value.goal) || textValue(value.direction) || title;
    return { number, title, goal };
  }
  const goal = summaryValue(value);
  return { number, title: fallbackTitle, goal };
}

function extrasFromContent(content: Record<string, unknown>): Record<string, unknown> {
  const extras: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(content)) {
    if (!knownContentKeys.has(key) && !candidateTitleKeys.includes(key as (typeof candidateTitleKeys)[number])) {
      extras[key] = value;
    }
  }
  return extras;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
```

- [ ] **Step 4: Run helper tests and verify pass**

Run:

```bash
pixi run npm --prefix frontend test -- blueprint-candidates.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit helper**

Run:

```bash
git status --short
git add frontend/src/features/open-book/blueprintCandidates.ts frontend/tests/blueprint-candidates.test.ts
git commit -m "Add blueprint candidate normalization"
```

Expected: commit includes only the helper and helper tests.

---

### Task 2: Candidate Workbench Component Tests

**Files:**
- Modify: `frontend/tests/blueprint-page.test.tsx`

- [ ] **Step 1: Replace old succeeded test with candidate workbench behavior**

In `frontend/tests/blueprint-page.test.tsx`, replace the test named `"renders succeeded blueprint title selection and accept action"` with:

```tsx
test("renders candidate workbench and accepts the selected candidate", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "succeeded",
          content: {
            title_options: ["长夜档案", "禁书回声"],
            genre: "奇幻",
            audience: "成人类型小说读者",
            selling_points: ["禁书悬疑"],
            reader_promises: ["真相反转"],
            protagonist: { name: "林既明", identity: "失意档案员", goal: "找回被禁书吞掉的记忆" },
            world: { summary: "禁书会吞噬记忆", rules: ["借阅要付出代价"] },
            central_conflict: "档案员追查禁书真相。",
            chapter_directions: [
              { title: "禁书初现", goal: "发现第一本会吞噬记忆的禁书" },
              { title: "借阅代价", goal: "确认同事失踪与借阅记录有关" },
              { title: "夜巡追捕", goal: "被图书馆夜巡者追捕" },
            ],
            candidates: [
              {
                title: "长夜档案",
                genre: "都市奇幻",
                selling_points: ["禁书代价", "记忆悬疑"],
              },
              {
                title: "禁书回声",
                audience: "悬疑推理读者",
                central_conflict: "修复师听见禁书里的求救声，并追查每一次回声背后的死者。",
                protagonist: { name: "沈回声", role: "禁书修复师" },
                selling_points: ["声音线索", "旧案反转"],
                chapter_directions: [
                  { title: "回声", goal: "听见第一本禁书里的求救声" },
                  { title: "借阅证", goal: "发现借阅记录被篡改" },
                  { title: "无声室", goal: "进入封存旧案的无声室" },
                ],
              },
            ],
          },
        }),
      }),
    )
    .mockResolvedValueOnce(Response.json({ bookId: 12, redirectTo: "/books/12" }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  expect(await screen.findByRole("tab", { name: /长夜档案/ })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: /禁书回声/ })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "候选方向对比" })).toHaveTextContent("都市奇幻");
  expect(screen.getByRole("table", { name: "候选方向对比" })).toHaveTextContent("前三章钩子");
  expect(screen.getByText("档案员追查禁书真相。")).toBeInTheDocument();
  expect(screen.getByText("林既明")).toBeInTheDocument();
  expect(screen.getByText("禁书初现")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("tab", { name: /禁书回声/ }));

  expect(screen.getByRole("tab", { name: /禁书回声/ })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("修复师听见禁书里的求救声，并追查每一次回声背后的死者。")).toBeInTheDocument();
  expect(screen.getByText("沈回声")).toBeInTheDocument();
  expect(screen.getByText("回声")).toBeInTheDocument();
  expect(screen.getByText("当前选择")).toBeInTheDocument();
  expect(screen.getByText("接受前预览")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "选定这个方向，进入项目页" }));

  await waitFor(() => expect(window.location.pathname).toBe("/books/12"));
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/blueprints/3/accept",
    expect.objectContaining({
      body: JSON.stringify({ selectedTitle: "禁书回声" }),
    }),
  );
});
```

- [ ] **Step 2: Update pending accept test names and button text**

In the test named `"accept action is disabled while request is pending"`, change:

```tsx
const acceptButton = await screen.findByRole("button", { name: "接受并进入项目页" });
```

to:

```tsx
const acceptButton = await screen.findByRole("button", { name: "选定这个方向，进入项目页" });
```

Keep the duplicate-click assertion unchanged.

- [ ] **Step 3: Update reset test labels and revision button text**

In the test named `"blueprint id changes reset title selection revision notes and action error"`, change label and button assertions:

```tsx
await waitFor(() => expect(screen.getByRole("tab", { name: /长夜档案/ })).toHaveAttribute("aria-selected", "true"));
fireEvent.click(screen.getByRole("tab", { name: /禁书回声/ }));
fireEvent.change(screen.getByLabelText("想让这一批怎么改"), {
  target: { value: "旧修订意见" },
});
fireEvent.click(screen.getByRole("button", { name: "按意见重生成一版" }));
await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("请填写修订方向。"));

rerender(<BlueprintPage blueprintId={4} />);

await waitFor(() => expect(screen.getByRole("tab", { name: /新蓝图/ })).toHaveAttribute("aria-selected", "true"));
expect(screen.getByLabelText("想让这一批怎么改")).toHaveValue("");
expect(screen.queryByRole("alert")).not.toBeInTheDocument();
```

- [ ] **Step 4: Add directed revision body test**

Add this test before `blueprintPayload`:

```tsx
test("revision action sends selected candidate context", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "succeeded",
          content: {
            title_options: ["长夜档案", "禁书回声"],
            central_conflict: "档案员追查禁书真相。",
            candidates: [
              { title: "长夜档案", genre: "奇幻" },
              { title: "禁书回声", genre: "悬疑" },
            ],
          },
        }),
      }),
    )
    .mockResolvedValueOnce(Response.json({ blueprintId: 4, redirectTo: "/blueprints/4" }, { status: 202 }));
  vi.stubGlobal("fetch", fetchMock);

  render(<BlueprintPage blueprintId={3} />);

  fireEvent.click(await screen.findByRole("tab", { name: /禁书回声/ }));
  fireEvent.change(screen.getByLabelText("想让这一批怎么改"), {
    target: { value: "保留回声设定，但前三章冲突更强" },
  });
  fireEvent.click(screen.getByRole("button", { name: "按意见重生成一版" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/blueprints/3/revise",
      expect.objectContaining({
        body: JSON.stringify({
          revisionNotes: "保留回声设定，但前三章冲突更强",
          selectedTitle: "禁书回声",
          selectedCandidateIndex: 1,
        }),
      }),
    ),
  );
});
```

- [ ] **Step 5: Add old global-only fallback test**

Add this test before `blueprintPayload`:

```tsx
test("renders old global-only blueprint fields as one candidate", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValueOnce(
      Response.json({
        blueprint: blueprintPayload({
          status: "succeeded",
          content: {
            title_options: ["长夜档案"],
            genre: "奇幻",
            audience: "成人",
            selling_points: ["禁书悬疑"],
            reader_promises: ["真相反转"],
            protagonist: "失意档案员",
            world: "禁书会吞噬记忆",
            central_conflict: "档案员追查禁书真相。",
            chapter_directions: [{ title: "第1章", goal: "发现禁书" }],
          },
        }),
      }),
    ),
  );

  render(<BlueprintPage blueprintId={3} />);

  expect(await screen.findByRole("tab", { name: /长夜档案/ })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("奇幻")).toBeInTheDocument();
  expect(screen.getByText("成人")).toBeInTheDocument();
  expect(screen.getByText("禁书悬疑")).toBeInTheDocument();
  expect(screen.getByText("真相反转")).toBeInTheDocument();
  expect(screen.getByText("失意档案员")).toBeInTheDocument();
  expect(screen.getByText("禁书会吞噬记忆")).toBeInTheDocument();
  expect(screen.getByText("发现禁书")).toBeInTheDocument();
});
```

- [ ] **Step 6: Run page tests and verify failure**

Run:

```bash
pixi run npm --prefix frontend test -- blueprint-page.test.tsx
```

Expected: FAIL because `BlueprintPage` still renders radio title choices, old labels, no comparison table, no accept preview, and no candidate context in revision body.

- [ ] **Step 7: Keep failing tests in the working tree**

Run:

```bash
git status --short
```

Expected: `frontend/tests/blueprint-page.test.tsx` is modified and the focused test failure from Step 6 is understood. Do not commit this failing state; Task 3 commits the tests together with the implementation.

---

### Task 3: Refactor Blueprint Page Into Candidate Workbench

**Files:**
- Modify: `frontend/src/features/open-book/BlueprintPage.tsx`

- [ ] **Step 1: Import candidate helpers**

At the top of `BlueprintPage.tsx`, update the React import and add helper imports:

```tsx
import { type CSSProperties, useEffect, useRef, useState } from "react";

import {
  type BlueprintCandidateView,
  fieldEntries,
  normalizeBlueprintCandidates,
  summaryValue,
} from "@/features/open-book/blueprintCandidates";
```

- [ ] **Step 2: Replace title state with selected candidate index**

Inside `BlueprintPage`, replace:

```tsx
const [selectedTitle, setSelectedTitle] = useState("");
```

with:

```tsx
const [selectedCandidateIndex, setSelectedCandidateIndex] = useState(0);
```

Inside the `useEffect` reset block, replace:

```tsx
setSelectedTitle("");
```

with:

```tsx
setSelectedCandidateIndex(0);
```

After fetch success, replace:

```tsx
const titles = titleOptions(response.blueprint.content);
setSelectedTitle(titles[0] ?? "");
```

with:

```tsx
setSelectedCandidateIndex(0);
```

- [ ] **Step 3: Compute candidates and selected candidate**

After:

```tsx
const titles = titleOptions(blueprint.content);
```

remove that line and add:

```tsx
const candidates = normalizeBlueprintCandidates(blueprint.content);
const selectedCandidate = candidates[selectedCandidateIndex] ?? candidates[0] ?? null;
```

- [ ] **Step 4: Replace succeeded JSX branch**

Replace the entire `blueprint.status === "succeeded"` JSX branch with:

```tsx
{blueprint.status === "succeeded" && (
  candidates.length > 0 && selectedCandidate ? (
    <div className="workbench-grid blueprint-workbench-grid">
      <section className="workbench-panel blueprint-content">
        <CandidateTabs
          candidates={candidates}
          onSelect={setSelectedCandidateIndex}
          selectedIndex={selectedCandidate.index}
        />
        <CandidateComparison
          candidates={candidates}
          onSelect={setSelectedCandidateIndex}
          selectedIndex={selectedCandidate.index}
        />
        <CandidateDetail candidate={selectedCandidate} />
      </section>

      <DecisionPanel
        blueprint={blueprint}
        candidate={selectedCandidate}
        pendingAction={pendingAction}
        revisionNotes={revisionNotes}
        setRevisionNotes={setRevisionNotes}
        onAccept={() =>
          void runAction("accept", `/api/blueprints/${blueprintId}/accept`, {
            selectedTitle: selectedCandidate.title,
          })
        }
        onRevise={() =>
          void runAction("revise", `/api/blueprints/${blueprintId}/revise`, {
            revisionNotes,
            selectedTitle: selectedCandidate.title,
            selectedCandidateIndex: selectedCandidate.index,
          })
        }
      />
    </div>
  ) : (
    <div className="workbench-panel workbench-panel--alert" role="alert">
      <h2>当前蓝图没有可用候选方向</h2>
      <p>模型返回内容里没有可选择的书名。可以重试生成，或查看模型原始返回排查问题。</p>
    </div>
  )
)}
```

- [ ] **Step 5: Add presentational components**

Add these components below `BlueprintPage` and above `isInProgress`:

```tsx
function CandidateTabs({
  candidates,
  onSelect,
  selectedIndex,
}: {
  candidates: BlueprintCandidateView[];
  onSelect: (index: number) => void;
  selectedIndex: number;
}) {
  return (
    <div className="blueprint-candidate-tabs" role="tablist" aria-label="候选方向">
      {candidates.map((candidate) => (
        <button
          aria-selected={selectedIndex === candidate.index}
          className={selectedIndex === candidate.index ? "is-active" : ""}
          key={`${candidate.index}-${candidate.title}`}
          onClick={() => onSelect(candidate.index)}
          role="tab"
          type="button"
        >
          <strong>{candidate.title}</strong>
          {candidate.genre && <span>{candidate.genre}</span>}
        </button>
      ))}
    </div>
  );
}

function CandidateComparison({
  candidates,
  onSelect,
  selectedIndex,
}: {
  candidates: BlueprintCandidateView[];
  onSelect: (index: number) => void;
  selectedIndex: number;
}) {
  const rows = [
    { label: "题材", value: (candidate: BlueprintCandidateView) => candidate.genre },
    { label: "目标读者", value: (candidate: BlueprintCandidateView) => candidate.audience },
    { label: "核心冲突", value: (candidate: BlueprintCandidateView) => candidate.centralConflict },
    { label: "主角定位", value: (candidate: BlueprintCandidateView) => summaryValue(candidate.protagonist) },
    {
      label: "前三章钩子",
      value: (candidate: BlueprintCandidateView) =>
        candidate.chapterDirections
          .slice(0, 3)
          .map((chapter) => chapter.goal || chapter.title)
          .filter(Boolean)
          .join(" / "),
    },
    { label: "主要卖点", value: (candidate: BlueprintCandidateView) => candidate.sellingPoints.slice(0, 3).join("、") },
  ];

  return (
    <div className="blueprint-comparison" aria-label="候选方向对比" role="table">
      <div className="blueprint-comparison__row blueprint-comparison__header" role="row">
        <span role="columnheader">对比项</span>
        {candidates.map((candidate) => (
          <button
            className={selectedIndex === candidate.index ? "is-active" : ""}
            key={candidate.title}
            onClick={() => onSelect(candidate.index)}
            role="columnheader"
            type="button"
          >
            {candidate.title}
          </button>
        ))}
      </div>
      {rows.map((row) => (
        <div className="blueprint-comparison__row" key={row.label} role="row">
          <strong role="rowheader">{row.label}</strong>
          {candidates.map((candidate) => (
            <span key={`${candidate.title}-${row.label}`} role="cell">
              {row.value(candidate) || "未提供"}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

function CandidateDetail({ candidate }: { candidate: BlueprintCandidateView }) {
  return (
    <article className="blueprint-candidate-detail">
      <header className="blueprint-direction-summary">
        <p className="eyebrow">当前方向</p>
        <h2>{candidate.centralConflict || candidate.title}</h2>
        <div className="blueprint-meta-strip">
          {candidate.genre && <span>{candidate.genre}</span>}
          {candidate.audience && <span>{candidate.audience}</span>}
        </div>
      </header>

      <section className="blueprint-info-section" aria-labelledby="blueprint-selling-points">
        <h3 id="blueprint-selling-points">卖点与读者承诺</h3>
        <ChipList items={candidate.sellingPoints} emptyText="未提供核心卖点" />
        <CompactList items={candidate.readerPromises} emptyText="未提供读者承诺" />
      </section>

      <div className="blueprint-two-column">
        <EntityPanel title="主角" value={candidate.protagonist} />
        <EntityPanel title="世界观" value={candidate.world} />
      </div>

      <section className="blueprint-info-section" aria-labelledby="blueprint-chapters">
        <h3 id="blueprint-chapters">前 10 章方向</h3>
        <ol className="blueprint-chapter-timeline">
          {candidate.chapterDirections.map((chapter) => (
            <li key={`${chapter.number}-${chapter.title}`}>
              <span>{String(chapter.number).padStart(2, "0")}</span>
              <div>
                <strong>{chapter.title}</strong>
                <p>{chapter.goal}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {Object.keys(candidate.extras).length > 0 && (
        <details className="blueprint-extra-fields">
          <summary>模型补充信息</summary>
          <KeyValueList value={candidate.extras} />
        </details>
      )}
    </article>
  );
}

function DecisionPanel({
  blueprint,
  candidate,
  pendingAction,
  revisionNotes,
  setRevisionNotes,
  onAccept,
  onRevise,
}: {
  blueprint: BlueprintPayload;
  candidate: BlueprintCandidateView;
  pendingAction: string | null;
  revisionNotes: string;
  setRevisionNotes: (value: string) => void;
  onAccept: () => void;
  onRevise: () => void;
}) {
  const firstHooks = candidate.chapterDirections.slice(0, 3);
  return (
    <aside className="workbench-panel blueprint-actions blueprint-decision-panel">
      <h2>决策面板</h2>
      <section className="blueprint-decision-block">
        <p className="eyebrow">当前选择</p>
        <strong>{candidate.title}</strong>
        <p>{[candidate.genre, candidate.audience].filter(Boolean).join(" · ") || "题材和读者未提供"}</p>
      </section>

      <section className="blueprint-decision-block">
        <p className="eyebrow">方向差异</p>
        <CompactList
          items={[
            candidate.sellingPoints.slice(0, 2).join("、"),
            candidate.centralConflict,
            firstHooks.map((chapter) => chapter.goal || chapter.title).join(" / "),
          ].filter(Boolean)}
          emptyText="暂无可提取的差异摘要"
        />
      </section>

      <label className="provider-field">
        想让这一批怎么改
        <textarea
          onChange={(event) => setRevisionNotes(event.target.value)}
          placeholder="保留当前方向，但主角更主动，前三章冲突更强"
          value={revisionNotes}
        />
      </label>
      <div className="blueprint-revision-prompts" aria-label="修订提示">
        <span>保留当前方向，加强前三章</span>
        <span>主角更主动</span>
        <span>融合另一个候选的世界观</span>
      </div>

      <details className="blueprint-accept-preview" open>
        <summary>接受前预览</summary>
        <KeyValueList
          value={{
            书名: candidate.title,
            题材: candidate.genre,
            目标读者: candidate.audience,
            核心冲突: candidate.centralConflict,
            主角: summaryValue(candidate.protagonist),
            世界观: summaryValue(candidate.world),
            前10章: candidate.chapterDirections.map((chapter) => chapter.title || chapter.goal).join(" / "),
          }}
        />
      </details>

      <button className="workbench-action-button" disabled={pendingAction !== null} onClick={onAccept} type="button">
        {pendingAction === "accept" ? (
          <AiWaitingIndicator label="进入项目中..." variant="inline" />
        ) : (
          "选定这个方向，进入项目页"
        )}
      </button>
      <button
        className="workbench-action-button workbench-action-button--secondary"
        disabled={pendingAction !== null}
        onClick={onRevise}
        type="button"
      >
        {pendingAction === "revise" ? (
          <AiWaitingIndicator label="提交修订中..." variant="inline" />
        ) : (
          "按意见重生成一版"
        )}
      </button>

      <details className="blueprint-extra-fields">
        <summary>模型原始信息</summary>
        <KeyValueList
          value={{
            蓝图版本: `v${blueprint.version}`,
            原始灵感: blueprint.idea,
            修订来源: blueprint.instruction ?? "无",
          }}
        />
      </details>
    </aside>
  );
}

function ChipList({ items, emptyText }: { items: string[]; emptyText: string }) {
  if (items.length === 0) {
    return <p>{emptyText}</p>;
  }
  return (
    <div className="blueprint-chip-list">
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </div>
  );
}

function CompactList({ items, emptyText }: { items: string[]; emptyText: string }) {
  const visibleItems = items.filter(Boolean);
  if (visibleItems.length === 0) {
    return <p>{emptyText}</p>;
  }
  return (
    <ul className="blueprint-compact-list">
      {visibleItems.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function EntityPanel({ title, value }: { title: string; value: unknown }) {
  const summary = summaryValue(value);
  const entries = fieldEntries(value);
  return (
    <section className="blueprint-entity-panel">
      <h3>{title}</h3>
      {summary ? <p>{summary}</p> : <p>未提供{title}信息</p>}
      {entries.length > 0 && <KeyValueList value={Object.fromEntries(entries)} />}
    </section>
  );
}

function KeyValueList({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value).filter(([, entryValue]) => summaryValue(entryValue));
  if (entries.length === 0) {
    return <p>暂无可显示信息</p>;
  }
  return (
    <dl className="blueprint-key-value">
      {entries.map(([key, entryValue]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{summaryValue(entryValue)}</dd>
        </div>
      ))}
    </dl>
  );
}
```

- [ ] **Step 6: Remove obsolete local helpers**

Delete the three obsolete helper declarations from the bottom of `BlueprintPage.tsx`: `BlueprintSummary`, `titleOptions`, and `textValue`. Keep `isInProgress` and `statusText` unchanged.

- [ ] **Step 7: Run page tests and align JSX**

Run:

```bash
pixi run npm --prefix frontend test -- blueprint-page.test.tsx
```

Expected: PASS. If it fails, fix the JSX labels, button text, or ARIA attributes in `BlueprintPage.tsx` to match the tested behavior; do not weaken the assertions.

- [ ] **Step 8: Commit page refactor after focused tests pass**

Run:

```bash
pixi run npm --prefix frontend test -- blueprint-page.test.tsx
git status --short
git add frontend/src/features/open-book/BlueprintPage.tsx frontend/tests/blueprint-page.test.tsx
git commit -m "Build blueprint candidate workbench"
```

Expected: `blueprint-page.test.tsx` passes before commit.

---

### Task 4: Workbench Styling

**Files:**
- Modify: `frontend/src/styles/globals.css`

- [ ] **Step 1: Add focused CSS after existing blueprint styles**

Append this CSS after the existing `.blueprint-page pre` block:

```css
.blueprint-workbench-grid {
  align-items: start;
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 24rem);
}

.blueprint-candidate-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
}

.blueprint-candidate-tabs button,
.blueprint-comparison button {
  border: 1px solid rgb(123 77 27 / 0.18);
  border-radius: 0.75rem;
  background: rgb(255 250 240 / 0.74);
  color: #40503b;
  cursor: pointer;
  padding: 0.65rem 0.8rem;
  text-align: left;
  transition:
    background 150ms ease,
    border-color 150ms ease,
    color 150ms ease;
}

.blueprint-candidate-tabs button {
  display: grid;
  gap: 0.25rem;
  min-width: min(100%, 10rem);
}

.blueprint-candidate-tabs button.is-active,
.blueprint-comparison button.is-active {
  border-color: rgb(123 77 27 / 0.42);
  background: #fff7e8;
  color: #6a4218;
}

.blueprint-candidate-tabs strong {
  color: #172018;
}

.blueprint-candidate-tabs span {
  color: #66705f;
  font-size: 0.78rem;
  font-weight: 800;
}

.blueprint-comparison {
  overflow-x: auto;
  border: 1px solid rgb(23 32 24 / 0.1);
  border-radius: 0.9rem;
  background: rgb(246 241 232 / 0.42);
}

.blueprint-comparison__row {
  display: grid;
  grid-template-columns: minmax(6rem, 8rem) repeat(var(--blueprint-candidate-count, 2), minmax(9rem, 1fr));
  min-width: 38rem;
}

.blueprint-comparison__row > * {
  border-bottom: 1px solid rgb(23 32 24 / 0.08);
  color: #4f5d4a;
  line-height: 1.45;
  padding: 0.75rem;
}

.blueprint-comparison__row:last-child > * {
  border-bottom: 0;
}

.blueprint-comparison__header > * {
  color: #213025;
  font-weight: 900;
}

.blueprint-candidate-detail,
.blueprint-info-section,
.blueprint-decision-panel,
.blueprint-decision-block {
  display: grid;
  gap: 1rem;
}

.blueprint-direction-summary {
  border: 1px solid rgb(53 99 66 / 0.16);
  border-radius: 0.9rem;
  background: #f4faef;
  padding: 1rem;
}

.blueprint-direction-summary h2 {
  max-width: none;
  font-size: clamp(1.35rem, 2vw, 1.8rem);
  line-height: 1.25;
}

.blueprint-meta-strip,
.blueprint-chip-list,
.blueprint-revision-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.blueprint-meta-strip span,
.blueprint-chip-list span,
.blueprint-revision-prompts span {
  border: 1px solid rgb(123 77 27 / 0.16);
  border-radius: 999px;
  background: rgb(255 250 240 / 0.82);
  color: #6a4218;
  font-size: 0.82rem;
  font-weight: 800;
  padding: 0.35rem 0.65rem;
}

.blueprint-two-column {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.blueprint-entity-panel,
.blueprint-extra-fields,
.blueprint-accept-preview {
  border: 1px solid rgb(23 32 24 / 0.1);
  border-radius: 0.9rem;
  background: rgb(255 250 240 / 0.58);
  padding: 1rem;
}

.blueprint-entity-panel h3,
.blueprint-info-section h3 {
  margin: 0;
  color: #213025;
  font-size: 1.05rem;
}

.blueprint-compact-list,
.blueprint-chapter-timeline {
  display: grid;
  gap: 0.55rem;
  margin: 0;
  padding-left: 1.1rem;
}

.blueprint-chapter-timeline {
  padding-left: 0;
  list-style: none;
}

.blueprint-chapter-timeline li {
  display: grid;
  grid-template-columns: 2.25rem minmax(0, 1fr);
  gap: 0.75rem;
  align-items: start;
  border-top: 1px solid rgb(23 32 24 / 0.08);
  padding-top: 0.75rem;
}

.blueprint-chapter-timeline li > span {
  border-radius: 999px;
  background: #e7f1df;
  color: #356342;
  font-size: 0.78rem;
  font-weight: 900;
  padding: 0.3rem 0;
  text-align: center;
}

.blueprint-chapter-timeline strong {
  color: #172018;
}

.blueprint-chapter-timeline p {
  margin: 0.2rem 0 0;
}

.blueprint-key-value {
  display: grid;
  gap: 0.55rem;
  margin: 0;
}

.blueprint-key-value div {
  display: grid;
  gap: 0.2rem;
}

.blueprint-key-value dt {
  color: #7b4d1b;
  font-size: 0.78rem;
  font-weight: 900;
}

.blueprint-key-value dd {
  margin: 0;
  color: #4f5d4a;
  line-height: 1.5;
}

.blueprint-extra-fields summary,
.blueprint-accept-preview summary {
  color: #33402f;
  cursor: pointer;
  font-weight: 900;
}
```

- [ ] **Step 2: Set comparison column count inline**

In `CandidateComparison`, update the root div:

```tsx
<div
  className="blueprint-comparison"
  aria-label="候选方向对比"
  role="table"
  style={{ "--blueprint-candidate-count": candidates.length } as CSSProperties}
>
```

This keeps the grid stable when the number of candidates changes.

- [ ] **Step 3: Add mobile CSS**

Inside the existing `@media (max-width: 720px)` block, add:

```css
.blueprint-workbench-grid,
.blueprint-two-column {
  grid-template-columns: 1fr;
}

.blueprint-candidate-tabs button {
  width: 100%;
}
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
pixi run npm --prefix frontend test -- blueprint-candidates.test.ts blueprint-page.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit styling**

Run:

```bash
git status --short
git add frontend/src/features/open-book/BlueprintPage.tsx frontend/src/styles/globals.css frontend/tests/blueprint-page.test.tsx
git commit -m "Style blueprint candidate workbench"
```

Expected: commit includes CSS and the small inline style update if it was not committed in Task 3.

---

### Task 5: Final Verification And Cleanup

**Files:**
- Verify: `frontend/src/features/open-book/BlueprintPage.tsx`
- Verify: `frontend/src/features/open-book/blueprintCandidates.ts`
- Verify: `frontend/src/styles/globals.css`
- Verify: `frontend/tests/blueprint-page.test.tsx`
- Verify: `frontend/tests/blueprint-candidates.test.ts`

- [ ] **Step 1: Run helper and page tests**

Run:

```bash
pixi run npm --prefix frontend test -- blueprint-candidates.test.ts blueprint-page.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run frontend typecheck**

Run:

```bash
pixi run npm --prefix frontend run typecheck
```

Expected: PASS with no TypeScript errors.

- [ ] **Step 3: Run frontend build**

Run:

```bash
pixi run npm --prefix frontend run build
```

Expected: PASS with Vite production output.

- [ ] **Step 4: Check source file lengths**

Run:

```bash
wc -l frontend/src/features/open-book/BlueprintPage.tsx frontend/src/features/open-book/blueprintCandidates.ts frontend/src/styles/globals.css frontend/tests/blueprint-page.test.tsx frontend/tests/blueprint-candidates.test.ts
```

Expected: no single file exceeds 1000 lines. If `BlueprintPage.tsx` exceeds 1000 lines, split presentational components into `frontend/src/features/open-book/BlueprintCandidateWorkbench.tsx` and rerun tests before continuing.

- [ ] **Step 5: Inspect changed files only**

Run:

```bash
git diff --stat
git diff -- frontend/src/features/open-book/BlueprintPage.tsx frontend/src/features/open-book/blueprintCandidates.ts frontend/src/styles/globals.css frontend/tests/blueprint-page.test.tsx frontend/tests/blueprint-candidates.test.ts
```

Expected: changes are limited to candidate workbench behavior, styling, and tests. Do not revert unrelated dirty files already present in the worktree.

- [ ] **Step 6: Final commit**

If Task 5 produced cleanup changes, run:

```bash
git add frontend/src/features/open-book/BlueprintPage.tsx frontend/src/features/open-book/blueprintCandidates.ts frontend/src/styles/globals.css frontend/tests/blueprint-page.test.tsx frontend/tests/blueprint-candidates.test.ts
git commit -m "Verify blueprint candidate workbench"
```

Expected: commit includes only cleanup changes from final verification. If there are no cleanup changes, skip this commit.
