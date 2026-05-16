# LLM Waiting Animations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shared accessible waiting animations to all LLM and AI job waits in the React workbench.

**Architecture:** Create one reusable waiting component under `frontend/src/components/feedback` and use it from pages that already track pending AI state. Add shared CSS in `globals.css` so existing workbench pages keep their current layout.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, CSS animations.

---

### Task 1: Shared Waiting Component

**Files:**
- Create: `frontend/src/components/feedback/AiWaitingIndicator.tsx`
- Modify: `frontend/src/styles/globals.css`
- Test: `frontend/tests/ai-waiting-indicator.test.tsx`

- [ ] **Step 1: Write failing component tests**

```tsx
render(<AiWaitingIndicator label="蓝图生成中" detail="模型正在组织故事结构。" />);
expect(screen.getByRole("status", { name: "蓝图生成中" })).toBeInTheDocument();
expect(screen.getByText("模型正在组织故事结构。")).toBeInTheDocument();
```

- [ ] **Step 2: Run the focused test**

Run: `pixi run -e frontend npm test -- ai-waiting-indicator.test.tsx`

Expected: fail because the component file does not exist yet.

- [ ] **Step 3: Implement the component and CSS**

Create a small role-aware component with `panel`, `inline`, and `message` variants. Add CSS classes for the pulse mark, scanning rail, compact inline label, and reduced-motion fallback.

- [ ] **Step 4: Run the focused test again**

Run: `pixi run -e frontend npm test -- ai-waiting-indicator.test.tsx`

Expected: pass.

### Task 2: Wire AI Waiting States

**Files:**
- Modify: `frontend/src/features/open-book/OpenBookPage.tsx`
- Modify: `frontend/src/features/open-book/BlueprintPage.tsx`
- Modify: `frontend/src/features/chapters/ChapterPage.tsx`
- Modify: `frontend/src/features/chapters/ChapterReviewActions.tsx`
- Modify: `frontend/src/features/books/BookWorkspacePage.tsx`
- Modify: `frontend/src/features/canon/TrustedStatePage.tsx`
- Modify: `frontend/src/features/quality/QualityPage.tsx`
- Modify: `frontend/src/features/provider-config/ProviderConfigPage.tsx`
- Test: existing feature tests plus `frontend/tests/quality-page.test.tsx`

- [ ] **Step 1: Add failing tests for representative waiting states**

Add assertions that `data-testid="ai-waiting-indicator"` appears while AI requests or AI polling states are active.

- [ ] **Step 2: Run the focused tests**

Run: `pixi run -e frontend npm test -- open-book-page.test.tsx blueprint-page.test.tsx chapter-page.test.tsx book-workspace-page.test.tsx trusted-state-page.test.tsx provider-config-page.test.tsx quality-page.test.tsx`

Expected: fail because pages still render plain text waiting states.

- [ ] **Step 3: Import and use `AiWaitingIndicator`**

Replace plain waiting strings and busy button labels for LLM/AI waits. Leave non-LLM busy states unchanged.

- [ ] **Step 4: Run the focused tests again**

Run: `pixi run -e frontend npm test -- open-book-page.test.tsx blueprint-page.test.tsx chapter-page.test.tsx book-workspace-page.test.tsx trusted-state-page.test.tsx provider-config-page.test.tsx quality-page.test.tsx`

Expected: pass.

### Task 3: Final Verification

**Files:**
- Verify all frontend changes.

- [ ] **Step 1: Run frontend test suite**

Run: `pixi run -e frontend npm test`

Expected: all Vitest tests pass.

- [ ] **Step 2: Run frontend build**

Run: `pixi run -e frontend npm run build`

Expected: TypeScript and Vite build pass.

- [ ] **Step 3: Check file lengths**

Run: `find frontend/src -type f \( -name '*.tsx' -o -name '*.ts' -o -name '*.css' \) -exec wc -l {} +`

Expected: no single source file exceeds 1000 lines.

