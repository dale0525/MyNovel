import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BootstrapGate } from "@/app/BootstrapGate";
import { ProviderConfigPage } from "@/features/provider-config/ProviderConfigPage";
import type { ProviderConfigDraft } from "@/features/provider-config/providerConfigTypes";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.pushState(null, "", "/");
});

test("provider setup requires chat and treats embedding as optional", () => {
  render(<ProviderConfigPage />);

  expect(screen.getByLabelText("Base url")).toBeRequired();
  expect(screen.getByLabelText("API key")).toBeRequired();
  expect(screen.getByLabelText("Model name")).toBeRequired();
  expect(screen.getByLabelText("Embedding model name")).not.toBeRequired();
  expect(screen.getByText("可选，不填时使用本地检索")).toBeInTheDocument();
  expect(screen.queryByLabelText("Rerank model name")).not.toBeInTheDocument();
});

test("embedding inherits credentials by default", () => {
  render(<ProviderConfigPage />);

  expect(
    screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"),
  ).toBeChecked();
  expect(screen.queryByLabelText("Embedding base url")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Embedding API key")).not.toBeInTheDocument();
});

test("dedicated embedding credentials are required only when embedding model is set", () => {
  render(<ProviderConfigPage />);

  fireEvent.click(screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"));
  expect(screen.getByLabelText("Embedding base url")).not.toBeRequired();
  expect(screen.getByLabelText("Embedding API key")).not.toBeRequired();

  fireEvent.change(screen.getByLabelText("Embedding model name"), {
    target: { value: "text-embedding-test" },
  });
  expect(screen.getByLabelText("Embedding base url")).toBeRequired();
  expect(screen.getByLabelText("Embedding API key")).toBeRequired();
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
                kind: "embedding",
                label: "Embedding",
                status: "failed",
                message: "embedding failed",
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
  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));

  await waitFor(() => expect(screen.getByText("embedding failed")).toBeInTheDocument());
  expect(screen.getByRole("alert")).toHaveTextContent("模型连接测试未全部通过。");
  expect(screen.getByRole("heading", { name: "连接你的 AI 模型" })).toBeInTheDocument();
});

test("saved config with failed optional embedding stays on setup with continue action", async () => {
  window.history.pushState(null, "", "/settings/provider");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        saved: true,
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
              kind: "embedding",
              label: "Embedding",
              status: "failed",
              message: "embedding failed",
            },
          ],
        },
      }),
    ),
  );

  render(<ProviderConfigPage />);

  fillRequiredFields();
  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));

  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(
      "配置已保存，但 Embedding 连接未通过；章节将使用本地检索。",
    ),
  );
  expect(screen.getByText("embedding failed")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "进入工作台" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/settings/provider");
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

  fireEvent.click(screen.getByLabelText("Embedding 使用 LLM 的 base url 和 api key"));
  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));

  await waitFor(() => expect(submitted).not.toBeNull());
  expect(submitted).toMatchObject({
    embeddingBaseUrl: "",
    embeddingApiKey: "",
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
                kind: "embedding",
                label: "Embedding",
                status: "failed",
                message: "embedding failed",
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
  await waitFor(() => expect(screen.getByText("embedding failed")).toBeInTheDocument());

  fireEvent.click(screen.getByRole("button", { name: "测试并保存配置" }));
  expect(screen.queryByText("embedding failed")).not.toBeInTheDocument();
  expect(screen.getByTestId("ai-waiting-indicator")).toHaveTextContent("正在测试...");

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

  expect(screen.getByLabelText("Embedding API key")).toHaveAttribute("autocomplete", "off");
});

test("configured settings page loads saved provider config without exposing api keys", async () => {
  window.history.pushState(null, "", "/settings/provider");
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input) === "/api/provider-config") {
      return Response.json({
        providerConfig: {
          llmBaseUrl: "https://api.saved.test/v1",
          llmModel: "gpt-saved",
          hasLlmApiKey: true,
          embeddingUseLlmCredentials: false,
          embeddingBaseUrl: "https://embedding.saved.test/v1",
          embeddingModel: "embedding-saved",
          hasEmbeddingApiKey: true,
          rerankUseLlmCredentials: true,
          rerankBaseUrl: null,
          rerankModel: null,
          hasRerankApiKey: false,
        },
        validated: true,
        embeddingValidated: true,
      });
    }
    return Response.json({}, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <BootstrapGate
      bootstrap={{ providerConfigured: true, initialRoute: "/settings/provider", message: null }}
    />,
  );

  await waitFor(() =>
    expect(screen.getByLabelText("Base url")).toHaveValue("https://api.saved.test/v1"),
  );
  expect(screen.getByLabelText("Model name")).toHaveValue("gpt-saved");
  expect(screen.getByLabelText("API key")).toHaveValue("");
  expect(screen.getByLabelText("API key")).not.toBeRequired();
  expect(screen.getByLabelText("Embedding model name")).toHaveValue("embedding-saved");
  expect(screen.getByLabelText("Embedding base url")).toHaveValue(
    "https://embedding.saved.test/v1",
  );
  expect(screen.getByLabelText("Embedding API key")).toHaveValue("");
  expect(screen.getByLabelText("Embedding API key")).not.toBeRequired();
  expect(screen.queryByText("已保存 API key；留空则继续使用，填写新值会替换。")).not.toBeInTheDocument();
  expect(screen.getAllByPlaceholderText("已保存，留空则继续使用")).toHaveLength(2);
  expect(document.body).not.toHaveTextContent("llm-secret");
  expect(fetchMock).toHaveBeenCalledWith("/api/provider-config", expect.anything());
});

test("BootstrapGate renders only setup when provider is not configured on any path", () => {
  window.history.pushState(null, "", "/books/new");

  render(
    <BootstrapGate
      bootstrap={{ providerConfigured: false, initialRoute: "/books/new", message: null }}
    />,
  );

  expect(screen.getByRole("heading", { name: "连接你的 AI 模型" })).toBeInTheDocument();
  expect(screen.queryByText("工作台")).not.toBeInTheDocument();
  expect(screen.queryByText("项目")).not.toBeInTheDocument();
  expect(screen.queryByText("开书页面将在后续任务接入")).not.toBeInTheDocument();
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
  expect(screen.getByRole("link", { name: "设置" })).toHaveAttribute("href", "/settings/provider");
  await waitFor(() => expect(screen.getByText("还没有作品")).toBeInTheDocument());
  expect(screen.getByRole("link", { name: "开始一本新书" })).toHaveAttribute(
    "href",
    "/books/new",
  );
});

test("BootstrapGate routes configured new-book path to the open-book page", () => {
  window.history.pushState(null, "", "/books/new");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(
    <BootstrapGate
      bootstrap={{ providerConfigured: true, initialRoute: "/books/new", message: null }}
    />,
  );

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "开一本新书" })).toBeInTheDocument();
  expect(screen.getByLabelText("故事灵感")).toBeInTheDocument();
  expect(screen.queryByText("开书页面将在后续任务接入。")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "把故事推进到下一步" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "开书" })).toHaveClass("is-active");
  expect(fetchMock).not.toHaveBeenCalled();
});

test("BootstrapGate routes configured blueprint path to the blueprint page", async () => {
  window.history.pushState(null, "", "/blueprints/8");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        blueprint: {
          id: 8,
          parentId: null,
          idea: "一座图书馆",
          version: 1,
          status: "pending",
          instruction: null,
          content: {},
          parseError: null,
          errorMessage: null,
        },
      }),
    ),
  );

  render(
    <BootstrapGate
      bootstrap={{ providerConfigured: true, initialRoute: "/blueprints/8", message: null }}
    />,
  );

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("蓝图排队中"));
  expect(screen.queryByText("项目页面将在后续任务接入。")).not.toBeInTheDocument();
});

test("BootstrapGate rerenders route after open-book submit navigation", async () => {
  window.history.pushState(null, "", "/books/new");
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path === "/api/open-book/stream") {
      return streamResponse([{ type: "done", blueprintId: 9, redirectTo: "/blueprints/9" }]);
    }
    if (path === "/api/blueprints/9") {
      return Response.json({
        blueprint: {
          id: 9,
          parentId: null,
          idea: "一座图书馆",
          version: 1,
          status: "pending",
          instruction: null,
          content: {},
          parseError: null,
          errorMessage: null,
        },
      });
    }
    return Response.json({}, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <BootstrapGate
      bootstrap={{ providerConfigured: true, initialRoute: "/books/new", message: null }}
    />,
  );

  fireEvent.change(screen.getByLabelText("故事灵感"), {
    target: { value: "失意档案员重建禁书图书馆" },
  });
  fireEvent.click(screen.getByRole("button", { name: "生成蓝图" }));

  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("蓝图排队中"));
  expect(window.location.pathname).toBe("/blueprints/9");
  expect(fetchMock).toHaveBeenCalledWith("/api/blueprints/9", expect.anything());
});

test("BootstrapGate rerenders route after blueprint revision navigation", async () => {
  window.history.pushState(null, "", "/blueprints/3");
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path === "/api/blueprints/3") {
      return Response.json({
        blueprint: {
          id: 3,
          parentId: null,
          idea: "一座图书馆",
          version: 1,
          status: "succeeded",
          instruction: null,
          content: { title_options: ["长夜档案"], premise: "档案员追查禁书真相。" },
          parseError: null,
          errorMessage: null,
        },
      });
    }
    if (path === "/api/blueprints/3/revise-stream") {
      return streamResponse([{ type: "done", blueprintId: 4, redirectTo: "/blueprints/4" }]);
    }
    if (path === "/api/blueprints/4") {
      return Response.json({
        blueprint: {
          id: 4,
          parentId: 3,
          idea: "一座图书馆",
          version: 2,
          status: "pending",
          instruction: "主角更疯一点",
          content: {},
          parseError: null,
          errorMessage: null,
        },
      });
    }
    return Response.json({}, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <BootstrapGate
      bootstrap={{ providerConfigured: true, initialRoute: "/blueprints/3", message: null }}
    />,
  );

  await waitFor(() => expect(screen.getByRole("tab", { name: /长夜档案/ })).toHaveAttribute("aria-selected", "true"));
  fireEvent.change(screen.getByLabelText("想让这一批怎么改"), {
    target: { value: "主角更疯一点" },
  });
  fireEvent.click(screen.getByRole("button", { name: "按意见重生成一版" }));

  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("蓝图排队中"));
  expect(window.location.pathname).toBe("/blueprints/4");
  expect(fetchMock).toHaveBeenCalledWith("/api/blueprints/4", expect.anything());
});

test("BootstrapGate refetches blueprint after same-route retry navigation", async () => {
  window.history.pushState(null, "", "/blueprints/3");
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path === "/api/blueprints/3") {
      const calls = fetchMock.mock.calls.filter(([calledPath]) => calledPath === path).length;
      return Response.json({
        blueprint: {
          id: 3,
          parentId: null,
          idea: "一座图书馆",
          version: 1,
          status: calls === 1 ? "failed" : "pending",
          instruction: null,
          content: {},
          parseError: calls === 1 ? "invalid json" : null,
          errorMessage: calls === 1 ? "模型没有返回 JSON" : null,
        },
      });
    }
    if (path === "/api/blueprints/3/retry-stream") {
      return streamResponse([{ type: "done", blueprintId: 3, redirectTo: "/blueprints/3" }]);
    }
    return Response.json({}, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <BootstrapGate
      bootstrap={{ providerConfigured: true, initialRoute: "/blueprints/3", message: null }}
    />,
  );

  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("模型没有返回 JSON"));
  fireEvent.click(screen.getByRole("button", { name: "重试生成" }));

  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("蓝图排队中"));
  expect(window.location.pathname).toBe("/blueprints/3");
  expect(fetchMock.mock.calls.filter(([path]) => path === "/api/blueprints/3")).toHaveLength(2);
});

test("BootstrapGate routes configured settings path inside the app shell", async () => {
  window.history.pushState(null, "", "/settings/provider");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({
        providerConfig: null,
        validated: false,
        embeddingValidated: false,
      }),
    ),
  );

  render(
    <BootstrapGate
      bootstrap={{ providerConfigured: true, initialRoute: "/settings/provider", message: null }}
    />,
  );

  expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "连接你的 AI 模型" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText("Base url")).toHaveValue(""));
  expect(screen.getByRole("link", { name: "设置" })).toHaveClass("is-active");
  expect(screen.queryByRole("heading", { name: "把故事推进到下一步" })).not.toBeInTheDocument();
});

test("BootstrapGate routes configured book path to the project workspace", async () => {
  window.history.pushState(null, "", "/books/42");
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input) === "/api/books/42") {
      return Response.json({
        book: {
          id: 42,
          title: "星港遗梦",
          genre: "科幻",
          audience: "成人",
          status: "draft",
          premise: "领航员追查失落星港的真相。",
        },
      });
    }
    return Response.json({}, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <BootstrapGate bootstrap={{ providerConfigured: true, initialRoute: "/books/42", message: null }} />,
  );

  await waitFor(() => expect(screen.getByRole("heading", { name: "星港遗梦" })).toBeInTheDocument());
  expect(screen.getByText("科幻 · 成人 · 草稿")).toBeInTheDocument();
  expect(screen.getByText("领航员追查失落星港的真相。")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "项目" })).toHaveClass("is-active");
  expect(fetchMock).toHaveBeenCalledWith("/api/books/42", expect.anything());
  expect(screen.queryByText("项目页面将在后续任务接入。")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "把故事推进到下一步" })).not.toBeInTheDocument();
});

test("BootstrapGate routes legacy review path to the workbench", () => {
  window.history.pushState(null, "", "/review");

  render(
    <BootstrapGate bootstrap={{ providerConfigured: true, initialRoute: "/review", message: null }} />,
  );

  expect(screen.getByRole("heading", { name: "把故事推进到下一步" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "质量复审" })).not.toBeInTheDocument();
});

function fillRequiredFields(overrides: Partial<ProviderConfigDraft> = {}) {
  const values = {
    llmBaseUrl: "https://api.example.test/v1",
    llmApiKey: "sk-test",
    llmModel: "gpt-test",
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
  if (values.embeddingModel !== undefined) {
    fireEvent.change(screen.getByLabelText("Embedding model name"), {
      target: { value: values.embeddingModel },
    });
  }
}

function streamResponse(events: Array<Record<string, unknown>>): Response {
  return new Response(events.map((event) => JSON.stringify(event)).join("\n"));
}
