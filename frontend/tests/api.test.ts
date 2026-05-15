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
