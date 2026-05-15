import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BootstrapGate } from "@/app/BootstrapGate";
import { ProviderConfigPage } from "@/features/provider-config/ProviderConfigPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("embedding and rerank inherit credentials by default", () => {
  render(<ProviderConfigPage />);

  expect(
    screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"),
  ).toBeChecked();
  expect(screen.getByLabelText("Rerank 使用 LLM 的 base url 和 api key")).toBeChecked();
  expect(screen.queryByLabelText("Embedding base url")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Embedding API key")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Rerank base url")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Rerank API key")).not.toBeInTheDocument();
});

test("unchecking inherited credentials shows dedicated fields", () => {
  render(<ProviderConfigPage />);

  fireEvent.click(screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"));
  fireEvent.click(screen.getByLabelText("Rerank 使用 LLM 的 base url 和 api key"));

  expect(screen.getByLabelText("Embedding base url")).toBeInTheDocument();
  expect(screen.getByLabelText("Embedding API key")).toBeInTheDocument();
  expect(screen.getByLabelText("Rerank base url")).toBeInTheDocument();
  expect(screen.getByLabelText("Rerank API key")).toBeInTheDocument();
});

test("failed validation stays on setup and renders validation messages", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        {
          error: {
            code: "provider_validation_failed",
            message: "模型连接测试未全部通过。",
            details: {},
          },
          saved: false,
          validation: {
            passed: false,
            results: [
              {
                kind: "llm",
                label: "LLM",
                status: "passed",
                message: "ok",
              },
              {
                kind: "rerank",
                label: "Rerank",
                status: "failed",
                message: "rerank failed",
              },
            ],
          },
        },
        { status: 400 },
      ),
    ),
  );

  render(<ProviderConfigPage />);

  fireEvent.change(screen.getByLabelText("Base url"), {
    target: { value: "https://api.example.test/v1" },
  });
  fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
  fireEvent.change(screen.getByLabelText("Model name"), { target: { value: "gpt-test" } });
  fireEvent.change(screen.getByLabelText("Embedding model name"), {
    target: { value: "embedding-test" },
  });
  fireEvent.change(screen.getByLabelText("Rerank model name"), {
    target: { value: "rerank-test" },
  });
  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));

  await waitFor(() => expect(screen.getByText("rerank failed")).toBeInTheDocument());
  expect(screen.getByRole("heading", { name: "连接你的 AI 模型" })).toBeInTheDocument();
});

test("BootstrapGate renders only setup when provider is not configured", () => {
  render(
    <BootstrapGate
      bootstrap={{ providerConfigured: false, initialRoute: "/setup", message: null }}
    />,
  );

  expect(screen.getByRole("heading", { name: "连接你的 AI 模型" })).toBeInTheDocument();
  expect(screen.queryByText("工作台")).not.toBeInTheDocument();
  expect(screen.queryByText("项目")).not.toBeInTheDocument();
});
