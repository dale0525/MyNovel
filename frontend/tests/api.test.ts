import { afterEach, expect, test, vi } from "vitest";

import { ApiError, getJson } from "@/lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("getJson rejects 2xx empty bodies with a controlled ApiError", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 200 })));

  await expect(getJson<{ ok: boolean }>("/api/empty")).rejects.toMatchObject({
    code: "empty_response",
  });
  await expect(getJson<{ ok: boolean }>("/api/empty")).rejects.toBeInstanceOf(ApiError);
});

test("getJson rejects 2xx non-JSON bodies with a controlled ApiError", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response("not json", {
          headers: { "Content-Type": "text/plain" },
          status: 200,
        }),
    ),
  );

  await expect(getJson<{ ok: boolean }>("/api/text")).rejects.toMatchObject({
    code: "invalid_json_response",
  });
  await expect(getJson<{ ok: boolean }>("/api/text")).rejects.toBeInstanceOf(ApiError);
});

test("getJson forwards abort signal to fetch", async () => {
  const controller = new AbortController();
  const fetchMock = vi.fn(async () => Response.json({ ok: true }));
  vi.stubGlobal("fetch", fetchMock);

  await getJson<{ ok: boolean }>("/api/ok", { signal: controller.signal });

  expect(fetchMock).toHaveBeenCalledWith("/api/ok", {
    headers: { Accept: "application/json" },
    signal: controller.signal,
  });
});
