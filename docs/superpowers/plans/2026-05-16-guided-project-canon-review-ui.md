# Guided Project Canon Review UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the project workspace, trusted-state page, and chapter review page into a visually guided flow with one primary action, impact previews, and advanced disclosures.

**Architecture:** Add small shared guidance components for identity bars, primary panels, impact panels, and disclosures. Then refactor each page around those primitives while keeping existing API payloads and endpoints. Tests drive the visible behavior first; implementation stays frontend-only unless an existing API shape cannot express the required state.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, CSS modules via global imports, lucide-react icons, pixi-managed Node environment.

---

## File Structure

- Create `frontend/src/components/guidance/GuidedPanels.tsx`: shared presentation primitives used by all three pages.
- Create `frontend/src/styles/guided-flow.css`: shared visual system for the guided layouts.
- Modify `frontend/src/styles/globals.css`: import the new CSS file after `workspace.css`.
- Modify `frontend/src/features/books/BookWorkspacePage.tsx`: replace the large hero and scattered controls with a guided current-action layout and advanced project tools disclosure.
- Modify `frontend/tests/book-workspace-page.test.tsx`: cover the new primary action states and collapsed tools.
- Modify `frontend/src/features/canon/TrustedStatePage.tsx`: split the page into section map, revision request panel, preview panel, and advanced details.
- Modify `frontend/tests/trusted-state-page.test.tsx`: cover section selection, locked sections, preview-gated apply actions, and advanced details.
- Modify `frontend/src/features/chapters/ChapterPage.tsx`: replace the hero-first review layout with result strip, manuscript, and decision panel.
- Modify `frontend/src/features/chapters/ChapterReviewActions.tsx`: convert the current all-actions panel into the decision panel with advanced controls.
- Modify `frontend/tests/chapter-page.test.tsx`: cover risk-based primary actions, impact preview, major-change confirmation, and running-state hiding of approval actions.
- Run existing frontend and backend checks after each page-level task.

## Task 1: Shared Guided UI Primitives

**Files:**
- Create: `frontend/src/components/guidance/GuidedPanels.tsx`
- Create: `frontend/src/styles/guided-flow.css`
- Modify: `frontend/src/styles/globals.css`
- Test: `frontend/tests/guided-panels.test.tsx`

- [ ] **Step 1: Write failing tests for the shared components**

Create `frontend/tests/guided-panels.test.tsx`:

```tsx
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import {
  AdvancedDisclosure,
  ImpactPanel,
  PrimaryActionPanel,
  ProjectIdentityBar,
} from "@/components/guidance/GuidedPanels";

afterEach(cleanup);

test("ProjectIdentityBar renders compact context without a page hero", () => {
  render(
    <ProjectIdentityBar
      eyebrow="Project"
      title="星港遗梦"
      meta={[
        { label: "状态", value: "生产中" },
        { label: "Canon", value: "v2" },
      ]}
    />,
  );

  expect(screen.getByRole("banner")).toHaveClass("guided-identity");
  expect(screen.getByText("星港遗梦")).toBeInTheDocument();
  expect(screen.getByText("状态")).toBeInTheDocument();
  expect(screen.getByText("生产中")).toBeInTheDocument();
  expect(screen.getByText("Canon")).toBeInTheDocument();
  expect(screen.getByText("v2")).toBeInTheDocument();
});

test("ImpactPanel renders visual impact items with tones", () => {
  render(
    <ImpactPanel
      title="影响预览"
      items={[
        { label: "可信设定", value: "不会直接写入", tone: "neutral" },
        { label: "下一步", value: "进入章节审核", tone: "good" },
        { label: "风险", value: "需要人工批准", tone: "warning" },
      ]}
    />,
  );

  expect(screen.getByRole("region", { name: "影响预览" })).toBeInTheDocument();
  expect(screen.getByText("不会直接写入")).toBeInTheDocument();
  expect(screen.getByText("进入章节审核")).toBeInTheDocument();
  expect(screen.getByText("需要人工批准")).toBeInTheDocument();
});

test("AdvancedDisclosure hides advanced content until opened", () => {
  render(
    <AdvancedDisclosure title="项目工具">
      <button type="button">批量生产</button>
    </AdvancedDisclosure>,
  );

  expect(screen.queryByRole("button", { name: "批量生产" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "项目工具" }));
  expect(screen.getByRole("button", { name: "批量生产" })).toBeInTheDocument();
});

test("PrimaryActionPanel keeps one visually dominant action area", () => {
  render(
    <PrimaryActionPanel
      eyebrow="Current"
      title="继续推进当前章节"
      summary="第 1 章正在等待生产。"
      action={<button type="button">运行当前章节</button>}
      impact={<ImpactPanel title="影响预览" items={[{ label: "结果", value: "生成候选正文" }]} />}
    />,
  );

  expect(screen.getByRole("heading", { name: "继续推进当前章节" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "运行当前章节" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "影响预览" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the failing shared component tests**

Run:

```bash
pixi run frontend-install
npm --prefix frontend run test -- guided-panels.test.tsx
```

Expected: FAIL because `@/components/guidance/GuidedPanels` does not exist.

- [ ] **Step 3: Create the shared component file**

Create `frontend/src/components/guidance/GuidedPanels.tsx`:

```tsx
import { ChevronDown } from "lucide-react";
import { type ReactNode, useState } from "react";

export type IdentityMetaItem = {
  label: string;
  value: ReactNode;
};

export type ImpactTone = "neutral" | "good" | "warning" | "danger";

export type ImpactItem = {
  label: string;
  value: ReactNode;
  tone?: ImpactTone;
};

type ProjectIdentityBarProps = {
  eyebrow: string;
  title: string;
  meta: IdentityMetaItem[];
  actions?: ReactNode;
};

export function ProjectIdentityBar({ eyebrow, title, meta, actions }: ProjectIdentityBarProps) {
  return (
    <header className="guided-identity" role="banner">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
      </div>
      <dl className="guided-identity__meta">
        {meta.map((item) => (
          <div key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
      {actions ? <div className="guided-identity__actions">{actions}</div> : null}
    </header>
  );
}

type ImpactPanelProps = {
  title: string;
  items: ImpactItem[];
};

export function ImpactPanel({ title, items }: ImpactPanelProps) {
  return (
    <section className="impact-panel" aria-label={title}>
      <h2>{title}</h2>
      <div className="impact-panel__grid">
        {items.map((item) => (
          <article className={`impact-item impact-item--${item.tone ?? "neutral"}`} key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}

type PrimaryActionPanelProps = {
  eyebrow: string;
  title: string;
  summary: ReactNode;
  action: ReactNode;
  impact: ReactNode;
  children?: ReactNode;
};

export function PrimaryActionPanel({
  eyebrow,
  title,
  summary,
  action,
  impact,
  children,
}: PrimaryActionPanelProps) {
  return (
    <section className="primary-action-panel" aria-labelledby="primary-action-title">
      <div className="primary-action-panel__main">
        <p className="eyebrow">{eyebrow}</p>
        <h2 id="primary-action-title">{title}</h2>
        <div className="primary-action-panel__summary">{summary}</div>
        <div className="primary-action-panel__action">{action}</div>
        {children}
      </div>
      <div className="primary-action-panel__impact">{impact}</div>
    </section>
  );
}

type AdvancedDisclosureProps = {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
};

export function AdvancedDisclosure({ title, children, defaultOpen = false }: AdvancedDisclosureProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="advanced-disclosure">
      <button
        aria-expanded={open}
        className="advanced-disclosure__toggle"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        <span>{title}</span>
        <ChevronDown aria-hidden="true" className={open ? "is-open" : ""} size={18} />
      </button>
      {open ? <div className="advanced-disclosure__content">{children}</div> : null}
    </section>
  );
}
```

- [ ] **Step 4: Add shared CSS and import it**

Create `frontend/src/styles/guided-flow.css`:

```css
.guided-identity {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: center;
  border: 1px solid rgb(23 32 24 / 0.1);
  border-radius: 1rem;
  background: rgb(255 252 245 / 0.78);
  box-shadow: 0 0.75rem 2rem rgb(43 52 35 / 0.08);
  padding: 1rem 1.15rem;
}

.guided-identity h1 {
  max-width: none;
  font-size: clamp(1.35rem, 3vw, 2.2rem);
  line-height: 1.08;
}

.guided-identity__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  justify-content: flex-end;
  margin: 0;
}

.guided-identity__meta div,
.status-block {
  border: 1px solid rgb(23 32 24 / 0.1);
  border-radius: 0.75rem;
  background: rgb(246 241 232 / 0.62);
  padding: 0.55rem 0.7rem;
}

.guided-identity__meta dt,
.status-block span,
.impact-item span {
  color: #596954;
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.guided-identity__meta dd {
  margin: 0.15rem 0 0;
  color: #172018;
  font-weight: 900;
}

.guided-identity__actions {
  justify-self: end;
}

.primary-action-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(17rem, 23rem);
  gap: 1rem;
  align-items: stretch;
  border: 1px solid rgb(53 99 66 / 0.18);
  border-radius: 1.25rem;
  background: rgb(255 252 245 / 0.82);
  box-shadow: 0 1.25rem 3rem rgb(43 52 35 / 0.1);
  padding: clamp(1rem, 3vw, 1.35rem);
}

.primary-action-panel__main,
.primary-action-panel__impact,
.impact-panel,
.advanced-disclosure__content {
  display: grid;
  gap: 1rem;
}

.primary-action-panel h2,
.impact-panel h2 {
  margin: 0;
  color: #172018;
  font-size: clamp(1.4rem, 2.4vw, 2rem);
}

.primary-action-panel__summary p {
  margin: 0;
}

.primary-action-panel__action {
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  align-items: center;
}

.impact-panel {
  border: 1px solid rgb(23 32 24 / 0.1);
  border-radius: 1rem;
  background: #fbfcf8;
  padding: 1rem;
}

.impact-panel__grid {
  display: grid;
  gap: 0.65rem;
}

.impact-item {
  border: 1px solid rgb(23 32 24 / 0.09);
  border-radius: 0.8rem;
  background: #fffdf8;
  padding: 0.75rem;
}

.impact-item strong {
  display: block;
  color: #172018;
  margin-top: 0.25rem;
}

.impact-item--good {
  border-color: rgb(53 99 66 / 0.22);
  background: #f4faef;
}

.impact-item--warning {
  border-color: rgb(191 127 39 / 0.28);
  background: #fff7e8;
}

.impact-item--danger {
  border-color: rgb(168 49 40 / 0.24);
  background: #fff2ed;
}

.advanced-disclosure {
  border: 1px solid rgb(23 32 24 / 0.1);
  border-radius: 1rem;
  background: rgb(255 252 245 / 0.62);
}

.advanced-disclosure__toggle {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  border: 0;
  background: transparent;
  color: #213025;
  cursor: pointer;
  font-weight: 900;
  padding: 0.9rem 1rem;
}

.advanced-disclosure__toggle svg {
  transition: transform 150ms ease;
}

.advanced-disclosure__toggle svg.is-open {
  transform: rotate(180deg);
}

.advanced-disclosure__content {
  border-top: 1px solid rgb(23 32 24 / 0.09);
  padding: 1rem;
}

@media (max-width: 840px) {
  .guided-identity,
  .primary-action-panel {
    grid-template-columns: 1fr;
  }

  .guided-identity__meta,
  .guided-identity__actions {
    justify-self: stretch;
  }
}
```

Modify the top of `frontend/src/styles/globals.css`:

```css
@import "./workspace.css";
@import "./guided-flow.css";
@import "./ai-waiting.css";
@import "./blueprint.css";
```

- [ ] **Step 5: Run shared component tests**

Run:

```bash
npm --prefix frontend run test -- guided-panels.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Run typecheck**

Run:

```bash
npm --prefix frontend run typecheck
```

Expected: PASS.

- [ ] **Step 7: Commit shared primitives**

Run:

```bash
git add frontend/src/components/guidance/GuidedPanels.tsx frontend/src/styles/guided-flow.css frontend/src/styles/globals.css frontend/tests/guided-panels.test.tsx
git commit -m "Add guided UI primitives"
```

## Task 2: Project Workspace Guided Flow

**Files:**
- Modify: `frontend/src/features/books/BookWorkspacePage.tsx`
- Modify: `frontend/tests/book-workspace-page.test.tsx`
- Modify: `frontend/src/styles/workspace.css`

- [ ] **Step 1: Add failing tests for guided workspace states**

Append these tests to `frontend/tests/book-workspace-page.test.tsx`:

```tsx
test("workspace surfaces a single review action when a chapter awaits review", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "awaiting_review" })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "继续推进项目" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "打开章节审核" })).toHaveAttribute("href", "/chapters/8");
  expect(screen.getByRole("region", { name: "影响预览" })).toHaveTextContent("审核后才会写入");
  expect(screen.queryByRole("button", { name: "批量生产" })).not.toBeInTheDocument();
});

test("workspace points blocked draft projects to trusted state instead of production", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ chapterStatus: "planned", includeLatestCanon: false })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "调整可信设定" })).toHaveAttribute("href", "/books/42/state");
  expect(screen.getByRole("region", { name: "影响预览" })).toHaveTextContent("不会启动章节生产");
  expect(screen.queryByRole("button", { name: "运行当前章节" })).not.toBeInTheDocument();
});

test("workspace keeps project tools collapsed until requested", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(bookPayload({ bookStatus: "canon_locked", chapterStatus: "planned", includeTrace: true, includeVolumePlan: true })),
    ),
  );

  render(<BookWorkspacePage bookId={42} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "批量生产" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("全书目标字数")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "项目工具" }));

  expect(screen.getByRole("button", { name: "批量生产" })).toBeInTheDocument();
  expect(screen.getByLabelText("全书目标字数")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "导出 Markdown" })).toHaveAttribute("href", "/api/books/42/export.md");
});
```

- [ ] **Step 2: Run workspace tests to verify failures**

Run:

```bash
npm --prefix frontend run test -- book-workspace-page.test.tsx
```

Expected: FAIL because the page still renders the old hero and always-visible project tools.

- [ ] **Step 3: Import shared primitives and derive workspace guidance**

In `frontend/src/features/books/BookWorkspacePage.tsx`, add imports:

```tsx
import {
  AdvancedDisclosure,
  ImpactPanel,
  type ImpactItem,
  PrimaryActionPanel,
  ProjectIdentityBar,
} from "@/components/guidance/GuidedPanels";
```

Add these helper types and functions near the existing helpers:

```tsx
type WorkspacePrimaryActionModel = {
  title: string;
  summary: string;
  action: React.ReactNode;
  impactItems: ImpactItem[];
};

function workspacePrimaryAction({
  bookId,
  currentTask,
  productionReady,
  actionBusy,
  runCurrentChapter,
}: {
  bookId: number;
  currentTask: ChapterPayload | null;
  productionReady: boolean;
  actionBusy: WorkspaceAction | null;
  runCurrentChapter: (chapter: ChapterPayload) => void;
}): WorkspacePrimaryActionModel {
  if (!productionReady) {
    return {
      title: "继续推进项目",
      summary: "可信设定还没有进入可生产状态。",
      action: (
        <a className="workbench-action-button" href={`/books/${bookId}/state`}>
          调整可信设定
        </a>
      ),
      impactItems: [
        { label: "章节生产", value: "不会启动章节生产", tone: "warning" },
        { label: "可信设定", value: "先完成定盘", tone: "neutral" },
        { label: "下一步", value: "回到项目继续生产", tone: "good" },
      ],
    };
  }

  if (!currentTask) {
    return {
      title: "继续推进项目",
      summary: "当前没有待推进章节。",
      action: (
        <a className="workbench-action-button" href={`/books/${bookId}/state`}>
          检查可信设定
        </a>
      ),
      impactItems: [
        { label: "章节队列", value: "暂无待生产章节", tone: "neutral" },
        { label: "可信设定", value: "保持现有版本", tone: "good" },
      ],
    };
  }

  if (currentTask.status === "awaiting_review") {
    return {
      title: "继续推进项目",
      summary: `第 ${currentTask.number} 章《${currentTask.title}》正在等待审核。`,
      action: (
        <a className="workbench-action-button" href={`/chapters/${currentTask.id ?? 0}`}>
          打开章节审核
        </a>
      ),
      impactItems: [
        { label: "可信设定", value: "审核后才会写入", tone: "warning" },
        { label: "正文", value: "先查看候选结果", tone: "neutral" },
        { label: "下一步", value: "批准或退回修订", tone: "good" },
      ],
    };
  }

  if (currentTask.status === "running") {
    return {
      title: "继续推进项目",
      summary: `第 ${currentTask.number} 章《${currentTask.title}》正在生成。`,
      action: (
        <a className="workbench-action-button" href={`/chapters/${currentTask.id ?? 0}`}>
          查看生成进度
        </a>
      ),
      impactItems: [
        { label: "AI", value: "正在处理", tone: "warning" },
        { label: "可信设定", value: "暂不写入", tone: "neutral" },
        { label: "下一步", value: "等待审核", tone: "good" },
      ],
    };
  }

  return {
    title: "继续推进项目",
    summary: `第 ${currentTask.number} 章《${currentTask.title}》可以开始生产。`,
    action: canRunChapter(currentTask) ? (
      <button
        className="workbench-action-button"
        disabled={actionBusy !== null}
        type="button"
        onClick={() => runCurrentChapter(currentTask)}
      >
        {actionBusy === "run-current" ? (
          <AiWaitingIndicator label="提交章节中..." variant="inline" />
        ) : (
          "运行当前章节"
        )}
      </button>
    ) : (
      <a className="workbench-action-button" href={`/chapters/${currentTask.id ?? 0}`}>
        打开当前章节
      </a>
    ),
    impactItems: [
      { label: "AI", value: "生成候选正文", tone: "good" },
      { label: "可信设定", value: "不会直接写入", tone: "neutral" },
      { label: "下一步", value: "进入章节审核", tone: "warning" },
    ],
  };
}
```

- [ ] **Step 4: Replace the workspace render structure**

Inside the ready-state render, compute the model:

```tsx
const primaryAction = workspacePrimaryAction({
  bookId,
  currentTask,
  productionReady,
  actionBusy,
  runCurrentChapter: (chapter) => void runCurrentChapter(chapter),
});
```

Replace the old hero plus three-column grid with:

```tsx
return (
  <section className="workbench-page book-workspace-page guided-workspace-page" aria-labelledby="book-workspace-title">
    <ProjectIdentityBar
      eyebrow="Project"
      title={book.title}
      meta={[
        { label: "题材", value: book.genre },
        { label: "读者", value: book.audience },
        { label: "状态", value: statusLabel(book.status) },
        { label: "Canon", value: latestCanon ? `v${latestCanon.version}` : "未定盘" },
      ]}
    />

    <PrimaryActionPanel
      eyebrow="Current"
      title={primaryAction.title}
      summary={<p>{primaryAction.summary}</p>}
      action={primaryAction.action}
      impact={<ImpactPanel title="影响预览" items={primaryAction.impactItems} />}
    />

    <section className="guided-status-strip" aria-labelledby="canon-summary-title">
      <div className="workspace-section-head">
        <div>
          <p className="eyebrow">Trusted State</p>
          <h2 id="canon-summary-title">可信设定摘要</h2>
        </div>
        <a className="workbench-secondary-link" href={`/books/${bookId}/state`}>
          查看可信设定
        </a>
      </div>
      <div className="workspace-foundation-grid">
        {canonSummaryCards(latestCanon?.content ?? {}).map((item) => (
          <a className="workspace-snapshot-card" href={`/books/${bookId}/state`} key={item.label}>
            <strong>{item.label}</strong>
            <p>{item.value}</p>
          </a>
        ))}
      </div>
    </section>

    <AdvancedDisclosure title="项目工具">
      {actionError ? (
        <section className="workspace-result-section workspace-result-section--alert" role="alert">
          {actionError}
        </section>
      ) : null}
      {actionStatus ? (
        <section className="workspace-result-section workspace-result-section--success" role="status">
          {actionStatus}
        </section>
      ) : null}

      <div className="guided-tools-grid">
        <section className="workspace-result-section" aria-labelledby="batch-production-title">
          <p className="eyebrow">Production</p>
          <h2 id="batch-production-title">批量生产</h2>
          {productionReady ? (
            <form className="chapter-action-form" onSubmit={(event) => void runBatchProduction(event)}>
              <label>
                批量章节数
                <input
                  max={10}
                  min={1}
                  type="number"
                  value={batchLimit}
                  onChange={(event) => setBatchLimit(clampedPositiveInt(event.target.value, 1, 10))}
                />
              </label>
              <button className="workbench-action-button" disabled={actionBusy !== null} type="submit">
                {actionBusy === "run-batch" ? (
                  <AiWaitingIndicator label="提交批量中..." variant="inline" />
                ) : (
                  "批量生产"
                )}
              </button>
            </form>
          ) : (
            <p>可信设定锁定后才能批量生产章节。</p>
          )}
        </section>

        <section className="workspace-result-section" aria-labelledby="word-target-title">
          <p className="eyebrow">Word Targets</p>
          <h2 id="word-target-title">目标字数</h2>
          <form className="chapter-action-form" onSubmit={(event) => void saveWordTargets(event)}>
            <label>
              全书目标字数
              <input
                min={1}
                type="number"
                value={targetWordCount}
                onChange={(event) => setTargetWordCount(clampedPositiveInt(event.target.value, 1))}
              />
            </label>
            <label>
              单章目标字数
              <input
                min={1}
                type="number"
                value={chapterWordCount}
                onChange={(event) => setChapterWordCount(clampedPositiveInt(event.target.value, 1))}
              />
            </label>
            <label className="chapter-major-change-toggle">
              <input
                checked={updateExistingChapters}
                type="checkbox"
                onChange={(event) => setUpdateExistingChapters(event.target.checked)}
              />
              同步更新已有章节计划
            </label>
            <button className="workbench-action-button" disabled={actionBusy !== null} type="submit">
              {actionBusy === "word-targets" ? "保存中..." : "保存目标字数"}
            </button>
          </form>
        </section>
      </div>

      <section aria-labelledby="chapter-queue-title">
        <div className="workspace-section-head">
          <div>
            <p className="eyebrow">Chapter Queue</p>
            <h2 id="chapter-queue-title">章节队列</h2>
          </div>
          <span>{chapters.length} 个章节</span>
        </div>
        <ol className="workspace-mini-list">
          {chapters.slice(0, 8).map((chapter) => (
            <li key={chapter.id ?? chapter.number}>
              <a className="workspace-mini-list-link" href={`/chapters/${chapter.id ?? 0}`}>
                第 {chapter.number} 章 · {chapter.title}
              </a>
              <span>{chapterStatusLabel(chapter.status)} · {chapter.wordCount} 字</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="workspace-result-section" aria-labelledby="workspace-actions-title">
        <p className="eyebrow">Controls</p>
        <h2 id="workspace-actions-title">导出与质量</h2>
        <div className="book-workspace-actions">
          <a className="workbench-action-button" href={`/books/${bookId}/quality`}>
            质量中心
          </a>
          <a className="workbench-secondary-link" href={`/api/books/${bookId}/export.md`}>
            导出 Markdown
          </a>
          <a className="workbench-secondary-link" href={`/api/books/${bookId}/export.json`}>
            导出 JSON
          </a>
        </div>
      </section>
    </AdvancedDisclosure>
  </section>
);
```

- [ ] **Step 5: Add workspace CSS for the new layout**

Append to `frontend/src/styles/workspace.css`:

```css
.guided-status-strip {
  display: grid;
  gap: 1rem;
  border: 1px solid rgb(23 32 24 / 0.1);
  border-radius: 1rem;
  background: rgb(255 252 245 / 0.68);
  padding: 1rem;
}

.guided-status-strip .workspace-snapshot-card {
  color: inherit;
  text-decoration: none;
}

.guided-tools-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

@media (max-width: 840px) {
  .guided-tools-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Update existing workspace assertions that depend on old always-visible tools**

In `frontend/tests/book-workspace-page.test.tsx`, for existing tests that click `批量生产`, `保存目标字数`, or check export links, open the disclosure first:

```tsx
fireEvent.click(screen.getByRole("button", { name: "项目工具" }));
```

Replace old assertions for `打开当前章节` in the default render test with:

```tsx
expect(screen.getByRole("link", { name: "查看生成进度" })).toHaveAttribute("href", "/chapters/8");
```

- [ ] **Step 7: Run workspace tests**

Run:

```bash
npm --prefix frontend run test -- book-workspace-page.test.tsx guided-panels.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Run typecheck**

Run:

```bash
npm --prefix frontend run typecheck
```

Expected: PASS.

- [ ] **Step 9: Commit workspace changes**

Run:

```bash
git add frontend/src/features/books/BookWorkspacePage.tsx frontend/src/styles/workspace.css frontend/tests/book-workspace-page.test.tsx
git commit -m "Guide project workspace primary flow"
```

## Task 3: Trusted State Section Map and Revision Preview

**Files:**
- Modify: `frontend/src/features/canon/TrustedStatePage.tsx`
- Modify: `frontend/tests/trusted-state-page.test.tsx`
- Modify: `frontend/src/styles/workspace.css`

- [ ] **Step 1: Add failing tests for the guided trusted-state workflow**

Append to `frontend/tests/trusted-state-page.test.tsx`:

```tsx
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
```

Modify the helper signature in the same test file:

```tsx
function trustedStatePayload({
  revisionStatus = "pending",
  selectedRevision = true,
}: {
  revisionStatus?: string;
  selectedRevision?: boolean;
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
    ],
    sectionLocks: { world_rules: true, characters: false, state_history: true },
    readiness: { complete: false, missingSections: ["characters"], messages: ["人物至少 3 条"] },
    pendingRevisions: selectedRevision ? [revision] : [],
    selectedRevision: selectedRevision ? revision : null,
  };
}
```

- [ ] **Step 2: Run trusted-state tests to verify failures**

Run:

```bash
npm --prefix frontend run test -- trusted-state-page.test.tsx
```

Expected: FAIL because the page still uses a select field and always-visible full content.

- [ ] **Step 3: Import shared primitives and track selected section**

In `frontend/src/features/canon/TrustedStatePage.tsx`, add:

```tsx
import {
  AdvancedDisclosure,
  ImpactPanel,
  type ImpactItem,
  ProjectIdentityBar,
} from "@/components/guidance/GuidedPanels";
```

Replace `targetSection` state with:

```tsx
const [selectedSectionKey, setSelectedSectionKey] = useState("characters");
```

In the successful load branch, set the first editable section:

```tsx
if (firstEditable) {
  setSelectedSectionKey(firstEditable.key);
}
```

In `reviseState`, submit:

```tsx
{ targetSection: selectedSectionKey, instruction }
```

- [ ] **Step 4: Add section map helpers**

Add below `RevisionPreviewActions`:

```tsx
function CanonSectionMap({
  sections,
  selectedKey,
  onSelect,
}: {
  sections: CanonSectionPayload[];
  selectedKey: string;
  onSelect: (key: string) => void;
}) {
  return (
    <section className="canon-section-map" aria-label="可信设定分区地图">
      {sections.map((section) => (
        <button
          className={section.key === selectedKey ? "canon-section-tile is-selected" : "canon-section-tile"}
          key={section.key}
          type="button"
          onClick={() => onSelect(section.key)}
        >
          <span>{section.label}</span>
          <strong>{sectionItemCount(section.content)} 条</strong>
          <em>{section.locked ? "已锁定" : section.editable ? "可修订" : "只读"}</em>
        </button>
      ))}
    </section>
  );
}

function selectedSectionImpact(section: CanonSectionPayload | null): ImpactItem[] {
  if (!section) {
    return [{ label: "分区", value: "未选择", tone: "neutral" }];
  }
  if (section.locked) {
    return [
      { label: "分区", value: section.label, tone: "neutral" },
      { label: "状态", value: "已锁定", tone: "warning" },
      { label: "修订", value: "不可提交", tone: "danger" },
    ];
  }
  return [
    { label: "分区", value: section.label, tone: "good" },
    { label: "提交结果", value: "只生成预览", tone: "neutral" },
    { label: "应用", value: "确认后才覆盖", tone: "warning" },
  ];
}

function sectionItemCount(content: unknown): number {
  return Array.isArray(content) ? content.length : content === null || content === undefined ? 0 : 1;
}
```

- [ ] **Step 5: Replace the trusted-state page layout**

In the ready render, compute:

```tsx
const selectedSection = canonSections.find((section) => section.key === selectedSectionKey) ?? null;
const revisionDisabled = submittingAction === "revise" || !selectedSection || selectedSection.locked || !selectedSection.editable;
```

Replace the old hero/content grid with:

```tsx
return (
  <section className="workbench-page canon-gate-layout guided-canon-page" aria-labelledby="trusted-state-title">
    <ProjectIdentityBar
      eyebrow="Trusted State"
      title="可信设定"
      meta={[
        { label: "项目", value: book.title },
        { label: "状态", value: statusLabel(book.status) },
        { label: "完整度", value: readiness.complete ? "可生产" : "需补全" },
      ]}
    />

    {actionState.status === "success" ? (
      <p className="setup-message" role="status">
        {actionState.message}
      </p>
    ) : null}
    {actionState.status === "error" ? (
      <p className="setup-message" role="alert">
        {actionState.message}
      </p>
    ) : null}

    <div className="guided-canon-grid">
      <main className="workbench-panel canon-gate-main">
        <div className={readiness.complete ? "canon-completion-gate trusted" : "canon-completion-gate"}>
          <h2>{readiness.complete ? "可信设定已完整" : "可信设定仍需补全"}</h2>
          {readiness.messages.length ? (
            <ul>
              {readiness.messages.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          ) : (
            <p>当前没有阻塞项。</p>
          )}
        </div>

        <CanonSectionMap
          sections={canonSections}
          selectedKey={selectedSectionKey}
          onSelect={(key) => setSelectedSectionKey(key)}
        />

        <AdvancedDisclosure title="完整设定内容">
          <section className="detail-state-sections" aria-label="可信设定分区">
            {canonSections.map((section) => (
              <article className="canon-section-panel data-card" id={section.anchor} key={section.key}>
                <header className="canon-section-head">
                  <div>
                    <p className="eyebrow">{section.key}</p>
                    <h2>{section.label}</h2>
                  </div>
                  <span className={section.locked ? "status-pill trusted" : "status-pill pending"}>
                    {section.locked ? "已锁定" : "可修订"}
                  </span>
                </header>
                <CanonSectionContent section={section} />
              </article>
            ))}
          </section>
        </AdvancedDisclosure>
      </main>

      <aside className="completion-aside guided-canon-aside">
        <section>
          <p className="eyebrow">Revision Request</p>
          <h2>生成修订预览</h2>
          <form className="canon-revision-form" onSubmit={(event) => void reviseState(event)}>
            <label>
              修订意图
              <textarea
                disabled={revisionDisabled}
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                placeholder="写一句你希望 AI 调整的方向"
              />
            </label>
            <button
              className="workbench-action-button"
              disabled={revisionDisabled || submittingAction !== null || instruction.trim().length === 0}
              type="submit"
            >
              {submittingAction === "revise" ? (
                <AiWaitingIndicator label="提交修订中..." variant="inline" />
              ) : (
                "生成修订预览"
              )}
            </button>
          </form>
        </section>

        <ImpactPanel title="影响预览" items={selectedSectionImpact(selectedSection)} />

        <RevisionPreview
          revision={selectedRevision}
          submittingAction={submittingAction}
          onApply={() => void applyRevision()}
          onDiscard={() => void discardRevision()}
        />
      </aside>
    </div>
  </section>
);
```

- [ ] **Step 6: Add guided trusted-state CSS**

Append to `frontend/src/styles/workspace.css`:

```css
.guided-canon-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(18rem, 24rem);
  gap: 1rem;
  align-items: start;
}

.canon-section-map {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: 0.75rem;
}

.canon-section-tile {
  display: grid;
  gap: 0.35rem;
  border: 1px solid rgb(23 32 24 / 0.1);
  border-radius: 0.9rem;
  background: #fffdf8;
  color: #172018;
  cursor: pointer;
  padding: 0.85rem;
  text-align: left;
}

.canon-section-tile.is-selected {
  border-color: rgb(53 99 66 / 0.36);
  background: #f4faef;
  box-shadow: inset 0 0.2rem 0 #356342;
}

.canon-section-tile span {
  font-weight: 900;
}

.canon-section-tile strong {
  color: #596954;
  font-size: 0.85rem;
}

.canon-section-tile em {
  color: #7b4d1b;
  font-size: 0.78rem;
  font-style: normal;
  font-weight: 900;
}

.guided-canon-aside {
  position: sticky;
  top: 1rem;
}

@media (max-width: 920px) {
  .guided-canon-grid {
    grid-template-columns: 1fr;
  }

  .guided-canon-aside {
    position: static;
  }
}
```

- [ ] **Step 7: Update existing trusted-state tests**

Replace old select usage:

```tsx
fireEvent.change(screen.getByLabelText("修订分区"), { target: { value: "characters" } });
```

with:

```tsx
fireEvent.click(screen.getByRole("button", { name: /人物/ }));
```

Replace label `修订指令` with `修订意图` in all test interactions.

- [ ] **Step 8: Run trusted-state tests**

Run:

```bash
npm --prefix frontend run test -- trusted-state-page.test.tsx guided-panels.test.tsx
```

Expected: PASS.

- [ ] **Step 9: Run typecheck**

Run:

```bash
npm --prefix frontend run typecheck
```

Expected: PASS.

- [ ] **Step 10: Commit trusted-state changes**

Run:

```bash
git add frontend/src/features/canon/TrustedStatePage.tsx frontend/src/styles/workspace.css frontend/tests/trusted-state-page.test.tsx
git commit -m "Guide trusted state revision flow"
```

## Task 4: Chapter Review Result Strip and Decision Panel

**Files:**
- Modify: `frontend/src/features/chapters/ChapterPage.tsx`
- Modify: `frontend/src/features/chapters/ChapterReviewActions.tsx`
- Modify: `frontend/tests/chapter-page.test.tsx`
- Modify: `frontend/src/styles/globals.css`

- [ ] **Step 1: Add failing tests for guided chapter review decisions**

Append to `frontend/tests/chapter-page.test.tsx`:

```tsx
test("chapter review shows result strip and trusted-state impact before approval", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload())));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByRole("region", { name: "章节结果" })).toHaveTextContent("状态变化");
  expect(screen.getByRole("region", { name: "将写入可信设定" })).toHaveTextContent("港湾");
  expect(screen.getByRole("button", { name: "批准并写入可信设定" })).toBeInTheDocument();
  expect(screen.queryByLabelText("手动修正文")).not.toBeInTheDocument();
});

test("chapter review prioritizes AI revision when audit risk is high", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ riskLevel: "high" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "让 AI 修订" })).toHaveClass("workbench-action-button");
  expect(screen.queryByRole("button", { name: "批准并写入可信设定" })).not.toBeInTheDocument();
});

test("major state changes require confirmation before approval", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ majorChange: true }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  const approveButton = screen.getByRole("button", { name: "批准并写入可信设定" });
  expect(approveButton).toBeDisabled();

  fireEvent.click(screen.getByLabelText("确认写入重大变化"));

  expect(approveButton).toBeEnabled();
});

test("running chapters hide approval decisions", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(chapterPayload({ status: "running" }))));

  render(<ChapterPage chapterId={12} />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "静默港湾" })).toBeInTheDocument());
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("章节生成中");
  expect(screen.queryByRole("button", { name: "批准并写入可信设定" })).not.toBeInTheDocument();
});
```

Extend the `chapterPayload` helper signature:

```tsx
function chapterPayload({
  status = "awaiting_review",
  emptyReview = false,
  revisedText = "岑星抵达静默港湾。",
  riskLevel = "low",
  majorChange = false,
}: {
  status?: string;
  emptyReview?: boolean;
  revisedText?: string;
  riskLevel?: string;
  majorChange?: boolean;
} = {}) {
```

Change the payload fields:

```tsx
auditReport: emptyReview ? {} : { risk_level: riskLevel, issues: riskLevel === "high" ? [{ title: "设定冲突", severity: "high", resolved: false }] : [] },
stateDelta: emptyReview ? {} : { chapter: 2, changes: [{ target: "港湾", change: "首次出现", major: majorChange }] },
```

- [ ] **Step 2: Run chapter tests to verify failures**

Run:

```bash
npm --prefix frontend run test -- chapter-page.test.tsx
```

Expected: FAIL because result strip, impact region, and gated approval do not exist.

- [ ] **Step 3: Add result and impact helpers in `ChapterPage.tsx`**

Add imports:

```tsx
import {
  ImpactPanel,
  type ImpactItem,
  ProjectIdentityBar,
} from "@/components/guidance/GuidedPanels";
```

Add helpers near the existing `ResultReport` helpers:

```tsx
function chapterResultItems(chapter: ChapterDetailPayload): ImpactItem[] {
  const changes = stateDeltaChanges(chapter.stateDelta);
  const issues = auditReportIssues(chapter.auditReport);
  const riskLevel = String(chapter.auditReport.risk_level ?? "未标注");
  return [
    { label: "正文", value: chapter.finalText || chapter.revisedText || chapter.draftText ? "已生成" : "未生成", tone: chapter.finalText || chapter.revisedText || chapter.draftText ? "good" : "warning" },
    { label: "审计", value: issues.length ? `${riskLevel} · ${issues.length} 项` : riskLevel, tone: riskLevel === "high" ? "danger" : "good" },
    { label: "状态变化", value: `${changes.length} 项`, tone: changes.length ? "warning" : "neutral" },
    { label: "重大变化", value: hasMajorStateChange(chapter.stateDelta) ? "需要确认" : "无", tone: hasMajorStateChange(chapter.stateDelta) ? "danger" : "good" },
  ];
}

function chapterImpactItems(chapter: ChapterDetailPayload): ImpactItem[] {
  const changes = stateDeltaChanges(chapter.stateDelta);
  if (!changes.length) {
    return [{ label: "可信设定", value: "无状态变化", tone: "neutral" }];
  }
  return changes.slice(0, 4).map((change) => ({
    label: String(change.target ?? "状态变化"),
    value: String(change.change ?? "将写入"),
    tone: change.major === true ? "danger" : "warning",
  }));
}

function hasHighRiskAudit(chapter: ChapterDetailPayload): boolean {
  if (chapter.auditReport.risk_level === "high") {
    return true;
  }
  return auditReportIssues(chapter.auditReport).some((issue) => issue.severity === "high" && issue.resolved !== true);
}

function hasMajorStateChange(stateDelta: Record<string, unknown>): boolean {
  if (stateDelta.majorChange === true) {
    return true;
  }
  if (Array.isArray(stateDelta.major_changes) && stateDelta.major_changes.length > 0) {
    return true;
  }
  return stateDeltaChanges(stateDelta).some((change) => change.major === true || change.severity === "major");
}
```

- [ ] **Step 4: Replace the chapter hero and result report placement**

In `ChapterPage.tsx`, replace the hero with:

```tsx
<ProjectIdentityBar
  eyebrow="Chapter Review"
  title={chapter.title}
  meta={[
    { label: "项目", value: book.title },
    { label: "章节", value: `第 ${chapter.number} 章` },
    { label: "状态", value: chapterStatusLabel(chapter.status) },
    { label: "Canon", value: latestCanon ? `v${latestCanon.version}` : "未连接" },
  ]}
/>
```

Replace the `ResultReport` call with:

```tsx
<ImpactPanel title="章节结果" items={chapterResultItems(chapter)} />
```

Pass new props into `ChapterReviewActions`:

```tsx
<ChapterReviewActions
  actionBusy={actionState.status === "submitting" ? actionState.action : null}
  chapter={chapter}
  highRisk={hasHighRiskAudit(chapter)}
  impactItems={chapterImpactItems(chapter)}
  majorChange={hasMajorStateChange(chapter.stateDelta)}
  onAction={(action, body) => void submitAction(action, body)}
/>
```

- [ ] **Step 5: Refactor `ChapterReviewActions` into a decision panel**

Update the props type in `frontend/src/features/chapters/ChapterReviewActions.tsx`:

```tsx
import { AdvancedDisclosure, ImpactPanel, type ImpactItem } from "@/components/guidance/GuidedPanels";

type ChapterReviewActionsProps = {
  chapter: ChapterDetailPayload;
  actionBusy: ChapterReviewAction | null;
  highRisk: boolean;
  impactItems: ImpactItem[];
  majorChange: boolean;
  onAction: (action: ChapterReviewAction, body: Record<string, unknown>) => void;
};
```

Replace the component body with this structure:

```tsx
export function ChapterReviewActions({
  chapter,
  actionBusy,
  highRisk,
  impactItems,
  majorChange,
  onAction,
}: ChapterReviewActionsProps) {
  const [manualText, setManualText] = useState(chapter.revisedText || chapter.draftText);
  const [manualNote, setManualNote] = useState("");
  const [repairNote, setRepairNote] = useState("");
  const [decisionNote, setDecisionNote] = useState("");
  const [allowMajorChanges, setAllowMajorChanges] = useState(false);

  useEffect(() => {
    setManualText(chapter.revisedText || chapter.draftText);
  }, [chapter.draftText, chapter.revisedText]);

  const canRun = chapter.status === "planned" || chapter.status === "needs_revision";
  const canReview = chapter.status === "awaiting_review";
  const canApprove = canReview && !highRisk && (!majorChange || allowMajorChanges);

  return (
    <section className="chapter-review-actions workbench-panel guided-decision-panel" aria-labelledby="chapter-actions-title">
      <div>
        <p className="eyebrow">Decision</p>
        <h2 id="chapter-actions-title">审核决定</h2>
      </div>

      {canRun ? (
        <button
          className="workbench-action-button"
          disabled={actionBusy !== null}
          type="button"
          onClick={() => onAction("run", {})}
        >
          {actionBusy === "run" ? (
            <AiWaitingIndicator label="提交运行中..." variant="inline" />
          ) : (
            "运行本章"
          )}
        </button>
      ) : null}

      {chapter.status === "running" ? (
        <AiWaitingIndicator
          detail="章节还在生成，完成后这里会出现审核决定。"
          label="章节生成中"
          variant="message"
        />
      ) : null}

      {canReview ? (
        <>
          <ImpactPanel title="将写入可信设定" items={impactItems} />

          {highRisk ? (
            <form
              className="chapter-action-form"
              onSubmit={(event) => {
                event.preventDefault();
                onAction("repair", { reviewerNote: repairNote });
              }}
            >
              <label>
                修订意图
                <textarea
                  value={repairNote}
                  onChange={(event) => setRepairNote(event.target.value)}
                  placeholder="写一句希望 AI 优先修复的方向"
                />
              </label>
              <button className="workbench-action-button" disabled={actionBusy !== null} type="submit">
                {actionBusy === "repair" ? (
                  <AiWaitingIndicator label="提交修订中..." variant="inline" />
                ) : (
                  "让 AI 修订"
                )}
              </button>
            </form>
          ) : null}

          {!highRisk && majorChange ? (
            <label className="chapter-major-change-toggle">
              <input
                checked={allowMajorChanges}
                type="checkbox"
                onChange={(event) => setAllowMajorChanges(event.target.checked)}
              />
              确认写入重大变化
            </label>
          ) : null}

          {!highRisk ? (
            <button
              className="workbench-action-button"
              disabled={actionBusy !== null || !canApprove}
              type="button"
              onClick={() =>
                onAction("approve", {
                  reviewerNote: decisionNote,
                  allowMajorChanges,
                })
              }
            >
              {actionBusy === "approve" ? "批准中..." : "批准并写入可信设定"}
            </button>
          ) : null}

          <form
            className="chapter-action-form"
            onSubmit={(event) => {
              event.preventDefault();
              onAction("request-revision", { reviewerNote: decisionNote });
            }}
          >
            <label>
              决策说明
              <input value={decisionNote} onChange={(event) => setDecisionNote(event.target.value)} />
            </label>
            <button className="workbench-secondary-button" disabled={actionBusy !== null} type="submit">
              {actionBusy === "request-revision" ? "退回中..." : "退回修订"}
            </button>
          </form>
        </>
      ) : null}

      <AdvancedDisclosure title="高级审核工具">
        <form
          className="chapter-action-form"
          onSubmit={(event) => {
            event.preventDefault();
            onAction("edit", { revisedText: manualText, reviewerNote: manualNote });
          }}
        >
          <label>
            手动修正文
            <textarea value={manualText} onChange={(event) => setManualText(event.target.value)} />
          </label>
          <label>
            修正说明
            <input value={manualNote} onChange={(event) => setManualNote(event.target.value)} />
          </label>
          <button className="workbench-secondary-button" disabled={actionBusy !== null} type="submit">
            {actionBusy === "edit" ? "保存中..." : "保存手动修正"}
          </button>
        </form>

        {!highRisk ? (
          <form
            className="chapter-action-form"
            onSubmit={(event) => {
              event.preventDefault();
              onAction("repair", { reviewerNote: repairNote });
            }}
          >
            <label>
              修订意图
              <textarea
                value={repairNote}
                onChange={(event) => setRepairNote(event.target.value)}
                placeholder="写一句希望 AI 优先修复的方向"
              />
            </label>
            <button className="workbench-secondary-button" disabled={actionBusy !== null} type="submit">
              {actionBusy === "repair" ? (
                <AiWaitingIndicator label="提交修订中..." variant="inline" />
              ) : (
                "让 AI 修订"
              )}
            </button>
          </form>
        ) : null}

        <a className="workbench-secondary-link" href={`/api/chapters/${chapter.id ?? 0}/export.txt`}>
          导出正文
        </a>
      </AdvancedDisclosure>
    </section>
  );
}
```

- [ ] **Step 6: Add decision panel CSS**

Append to `frontend/src/styles/globals.css`:

```css
.guided-decision-panel {
  position: sticky;
  top: 1rem;
}

.guided-decision-panel .impact-panel {
  background: #fbfcf8;
}

@media (max-width: 720px) {
  .guided-decision-panel {
    position: static;
  }
}
```

- [ ] **Step 7: Update existing chapter tests**

For the existing test `"chapter review actions call edit repair approve and export endpoints"`:

1. Open advanced tools before manual edit:

```tsx
fireEvent.click(screen.getByRole("button", { name: "高级审核工具" }));
```

2. Replace approval button name:

```tsx
fireEvent.click(screen.getByRole("button", { name: "批准并写入可信设定" }));
```

3. Keep export assertion after advanced tools are open:

```tsx
expect(screen.getByRole("link", { name: "导出正文" })).toHaveAttribute("href", "/api/chapters/12/export.txt");
```

For the repair pending test, use the visible main `让 AI 修订` only when high risk. Change the payload setup:

```tsx
.mockResolvedValueOnce(Response.json(chapterPayload({ riskLevel: "high" })))
```

and replace label `修复要求` with `修订意图`.

- [ ] **Step 8: Run chapter tests**

Run:

```bash
npm --prefix frontend run test -- chapter-page.test.tsx guided-panels.test.tsx
```

Expected: PASS.

- [ ] **Step 9: Run typecheck**

Run:

```bash
npm --prefix frontend run typecheck
```

Expected: PASS.

- [ ] **Step 10: Commit chapter review changes**

Run:

```bash
git add frontend/src/features/chapters/ChapterPage.tsx frontend/src/features/chapters/ChapterReviewActions.tsx frontend/src/styles/globals.css frontend/tests/chapter-page.test.tsx
git commit -m "Guide chapter review decisions"
```

## Task 5: Visual QA and Full Verification

**Files:**
- Modify only if verification exposes a concrete issue in files touched by Tasks 1-4.

- [ ] **Step 1: Run the targeted frontend suite**

Run:

```bash
npm --prefix frontend run test -- guided-panels.test.tsx book-workspace-page.test.tsx trusted-state-page.test.tsx chapter-page.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run all frontend unit tests**

Run:

```bash
npm --prefix frontend run test
```

Expected: PASS.

- [ ] **Step 3: Run frontend typecheck**

Run:

```bash
npm --prefix frontend run typecheck
```

Expected: PASS.

- [ ] **Step 4: Run frontend lint**

Run:

```bash
npm --prefix frontend run lint
```

Expected: PASS.

- [ ] **Step 5: Run production build**

Run:

```bash
npm --prefix frontend run build
```

Expected: PASS.

- [ ] **Step 6: Run the backend tests that cover API payload compatibility**

Run:

```bash
pixi run pytest tests/test_workbench_api.py tests/test_book_state_api.py tests/test_chapter_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Start the dev server for manual browser verification**

Run:

```bash
pixi run dev
```

Expected: server starts and prints local frontend/backend URLs. Keep the session running until manual verification is done.

- [ ] **Step 8: Verify desktop and mobile layout in the browser**

Open the local URL from Step 7. Check these routes at desktop width and mobile width:

- `/books/42`
- `/books/42/state`
- `/chapters/12`

Expected:

- Project page shows compact identity, one dominant current action, and collapsed project tools.
- Trusted-state page shows section map, revision panel, impact preview, and collapsed full content.
- Chapter page shows result strip, manuscript, decision panel, and collapsed advanced tools.
- No text overlaps at 375px, 768px, 1024px, or 1440px widths.
- Buttons fit their containers.
- Advanced disclosures open and close without shifting unrelated sections unexpectedly.

- [ ] **Step 9: Stop the dev server**

If Step 7 is still running in an exec session, stop it with `Ctrl-C`.

- [ ] **Step 10: Commit verification fixes if any were needed**

If Step 8 required CSS or test adjustments, commit only those changes:

```bash
git add frontend/src frontend/tests
git commit -m "Polish guided review UI"
```

If no changes were needed, do not create an empty commit.

## Self-Review

Spec coverage:

- Project page next-action clarity is covered by Task 2.
- Trusted-state section selection, AI-first revision, and preview-gated apply are covered by Task 3.
- Chapter review impact-before-decision and risk-based primary action are covered by Task 4.
- Progressive disclosure for advanced user tools is covered in Tasks 1-4.
- Visual verification across responsive sizes is covered by Task 5.

Placeholder scan:

- The plan contains no placeholder markers or deferred implementation instructions.
- Each code-changing task includes test code, implementation snippets, commands, expected results, and commit commands.

Type consistency:

- Shared types are exported from `GuidedPanels.tsx` and imported where used.
- `ImpactItem` is used consistently by project, trusted-state, and chapter pages.
- Existing endpoint names and action names are preserved.
