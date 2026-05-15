export type ApiErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

export class ApiError extends Error {
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly payload: unknown;

  constructor(message: string, code: string, details: Record<string, unknown>, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.details = details;
    this.payload = payload;
  }
}

type ApiRequestOptions = {
  signal?: AbortSignal;
};

export async function getJson<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const init: RequestInit = {
    headers: { Accept: "application/json" },
  };
  if (options.signal) {
    init.signal = options.signal;
  }
  const response = await fetch(path, init);
  return parseJsonResponse<T>(response);
}

export async function postJson<T>(
  path: string,
  body: unknown,
  options: ApiRequestOptions = {},
): Promise<T> {
  const init: RequestInit = {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  };
  if (options.signal) {
    init.signal = options.signal;
  }
  const response = await fetch(path, init);
  return parseJsonResponse<T>(response);
}

export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const parsed = await readJsonPayload(response);
  const payload = parsed.kind === "json" ? parsed.payload : null;
  if (!response.ok) {
    const error = apiErrorBody(payload).error;
    throw new ApiError(
      error?.message ?? "请求失败。",
      error?.code ?? "request_failed",
      error?.details ?? {},
      payload,
    );
  }
  if (parsed.kind === "empty") {
    throw new ApiError("API 返回了空响应。", "empty_response", {}, payload);
  }
  if (parsed.kind === "invalid") {
    throw new ApiError("API 返回了无效 JSON。", "invalid_json_response", {}, payload);
  }
  return payload as T;
}

type JsonPayloadResult =
  | { kind: "json"; payload: unknown }
  | { kind: "empty" }
  | { kind: "invalid" };

async function readJsonPayload(response: Response): Promise<JsonPayloadResult> {
  const text = await response.text();
  if (!text) {
    return { kind: "empty" };
  }
  try {
    return { kind: "json", payload: JSON.parse(text) as unknown };
  } catch {
    return { kind: "invalid" };
  }
}

function apiErrorBody(payload: unknown): ApiErrorBody {
  if (payload === null || typeof payload !== "object") {
    return {};
  }
  return payload as ApiErrorBody;
}
