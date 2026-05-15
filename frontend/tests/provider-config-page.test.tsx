import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BootstrapGate } from "@/app/BootstrapGate";
import { ProviderConfigPage } from "@/features/provider-config/ProviderConfigPage";
import type { ProviderConfigDraft } from "@/features/provider-config/providerConfigTypes";

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
  expect(screen.getByRole("alert")).toHaveTextContent("模型连接测试未全部通过。");
  expect(screen.getByRole("heading", { name: "连接你的 AI 模型" })).toBeInTheDocument();
});

test("malformed validation error payload does not crash the setup page", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json(
        {
          error: {
            code: "provider_validation_failed",
            message: "malformed validation response",
            details: {},
          },
          validation: { passed: false, results: "not an array" },
        },
        { status: 400 },
      ),
    ),
  );

  render(<ProviderConfigPage />);

  fillRequiredFields();
  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));

  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("malformed validation response"),
  );
  expect(screen.queryByText("模型连接结果")).not.toBeInTheDocument();
});

test("submit sanitizes hidden inherited credential fields", async () => {
  let submitted: ProviderConfigDraft | null = null;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_path: string | URL | Request, init?: RequestInit) => {
      submitted = JSON.parse(String(init?.body)) as ProviderConfigDraft;
      return Response.json(
        {
          error: {
            code: "provider_validation_failed",
            message: "模型连接测试未全部通过。",
            details: {},
          },
          validation: { passed: false, results: [] },
        },
        { status: 400 },
      );
    }),
  );

  render(<ProviderConfigPage />);

  fillRequiredFields();
  fireEvent.click(screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"));
  fireEvent.change(screen.getByLabelText("Embedding base url"), {
    target: { value: "https://embedding.example.test/v1" },
  });
  fireEvent.change(screen.getByLabelText("Embedding API key"), {
    target: { value: "embedding-secret" },
  });
  fireEvent.click(screen.getByLabelText("Rerank 使用 LLM 的 base url 和 api key"));
  fireEvent.change(screen.getByLabelText("Rerank base url"), {
    target: { value: "https://rerank.example.test/v1" },
  });
  fireEvent.change(screen.getByLabelText("Rerank API key"), {
    target: { value: "rerank-secret" },
  });

  fireEvent.click(screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"));
  fireEvent.click(screen.getByLabelText("Rerank 使用 LLM 的 base url 和 api key"));
  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));

  await waitFor(() => expect(submitted).not.toBeNull());
  expect(submitted).toMatchObject({
    embeddingBaseUrl: "",
    embeddingApiKey: "",
    rerankBaseUrl: "",
    rerankApiKey: "",
  });
});

test("client-side redaction handles overlapping secrets without leaking suffixes", async () => {
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
          validation: {
            passed: false,
            results: [
              {
                kind: "embedding",
                label: "Embedding",
                status: "failed",
                message: "embedding key abc123 failed and llm key abc failed",
              },
            ],
          },
        },
        { status: 400 },
      ),
    ),
  );

  render(<ProviderConfigPage />);

  fillRequiredFields({ llmApiKey: "abc" });
  fireEvent.click(screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"));
  fireEvent.change(screen.getByLabelText("Embedding base url"), {
    target: { value: "https://embedding.example.test/v1" },
  });
  fireEvent.change(screen.getByLabelText("Embedding API key"), {
    target: { value: "abc123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));

  await waitFor(() =>
    expect(
      screen.getByText("embedding key [redacted] failed and llm key [redacted] failed"),
    ).toBeInTheDocument(),
  );
  expect(screen.queryByText("123", { exact: false })).not.toBeInTheDocument();
});

test("a new submit clears stale validation while the next request is pending", async () => {
  let resolveSecond: (response: Response) => void = () => {};
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json(
        {
          error: {
            code: "provider_validation_failed",
            message: "模型连接测试未全部通过。",
            details: {},
          },
          validation: {
            passed: false,
            results: [
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
    )
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveSecond = resolve;
        }),
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<ProviderConfigPage />);

  fillRequiredFields();
  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));
  await waitFor(() => expect(screen.getByText("rerank failed")).toBeInTheDocument());

  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));
  expect(screen.queryByText("rerank failed")).not.toBeInTheDocument();

  resolveSecond(
    Response.json(
      {
        error: {
          code: "provider_validation_failed",
          message: "模型连接测试未全部通过。",
          details: {},
        },
        validation: { passed: false, results: [] },
      },
      { status: 400 },
    ),
  );
});

test("api key fields disable browser autocomplete", () => {
  render(<ProviderConfigPage />);

  expect(screen.getByLabelText("API key")).toHaveAttribute("autocomplete", "off");

  fireEvent.click(screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"));
  fireEvent.click(screen.getByLabelText("Rerank 使用 LLM 的 base url 和 api key"));

  expect(screen.getByLabelText("Embedding API key")).toHaveAttribute("autocomplete", "off");
  expect(screen.getByLabelText("Rerank API key")).toHaveAttribute("autocomplete", "off");
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

test("BootstrapGate renders the workbench shell when provider is configured", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        books: [],
      }),
    ),
  );

  render(
    <BootstrapGate bootstrap={{ providerConfigured: true, initialRoute: "/", message: null }} />,
  );

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "工作台" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "开书" })).toHaveAttribute("href", "/books/new");
  expect(screen.getByRole("link", { name: "设置" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText("还没有作品")).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "开始一本新书" })).toHaveAttribute(
    "href",
    "/books/new",
  );
});

function fillRequiredFields(overrides: Partial<ProviderConfigDraft> = {}) {
  const values = {
    llmBaseUrl: "https://api.example.test/v1",
    llmApiKey: "sk-test",
    llmModel: "gpt-test",
    embeddingModel: "embedding-test",
    rerankModel: "rerank-test",
    ...overrides,
  };

  fireEvent.change(screen.getByLabelText("Base url"), {
    target: { value: values.llmBaseUrl },
  });
  fireEvent.change(screen.getByLabelText("API key"), {
    target: { value: values.llmApiKey },
  });
  fireEvent.change(screen.getByLabelText("Model name"), {
    target: { value: values.llmModel },
  });
  fireEvent.change(screen.getByLabelText("Embedding model name"), {
    target: { value: values.embeddingModel },
  });
  fireEvent.change(screen.getByLabelText("Rerank model name"), {
    target: { value: values.rerankModel },
  });
}
