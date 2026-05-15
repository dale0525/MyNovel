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

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
  });
  return parseJsonResponse<T>(response);
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return parseJsonResponse<T>(response);
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const payload = await readJsonPayload(response);
  if (!response.ok) {
    const error = apiErrorBody(payload).error;
    throw new ApiError(
      error?.message ?? "请求失败。",
      error?.code ?? "request_failed",
      error?.details ?? {},
      payload,
    );
  }
  return payload as T;
}

async function readJsonPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function apiErrorBody(payload: unknown): ApiErrorBody {
  if (payload === null || typeof payload !== "object") {
    return {};
  }
  return payload as ApiErrorBody;
}
