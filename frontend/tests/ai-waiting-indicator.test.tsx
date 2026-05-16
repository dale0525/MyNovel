import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { AiStreamFeedback } from "@/components/feedback/AiStreamFeedback";
import { AiWaitingIndicator } from "@/components/feedback/AiWaitingIndicator";

afterEach(() => {
  cleanup();
});

test("renders an accessible panel waiting indicator", () => {
  render(<AiWaitingIndicator label="蓝图生成中" detail="模型正在组织故事结构。" />);

  expect(screen.getByRole("status", { name: "蓝图生成中" })).toBeInTheDocument();
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("蓝图生成中");
  expect(screen.getByText("模型正在组织故事结构。")).toBeInTheDocument();
});

test("renders compact inline waiting copy for busy buttons", () => {
  render(<AiWaitingIndicator label="提交中..." variant="inline" />);

  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("提交中...");
});

test("renders an animated hero waiting status", () => {
  render(<AiWaitingIndicator label="蓝图生成中" variant="hero" />);

  expect(screen.getByRole("status", { name: "蓝图生成中" })).toHaveClass("ai-waiting--hero");
});

test("keeps a reserved stream feedback track before chunks arrive", () => {
  const { container } = render(<AiStreamFeedback snippets={[]} />);

  const feedback = container.querySelector(".ai-stream-feedback");
  expect(feedback).toHaveClass("is-idle");
  expect(feedback).toHaveAttribute("aria-hidden", "true");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
