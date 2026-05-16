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
