import { ApiError, getJson, postJson } from "@/lib/api";
import type {
  ProviderConfigDraft,
  ProviderConfigLoadResponse,
  ProviderConfigResponse,
  ProviderValidationReport,
  ProviderValidationResult,
} from "./providerConfigTypes";

export function getProviderConfig(options: { signal?: AbortSignal } = {}) {
  return getJson<ProviderConfigLoadResponse>("/api/provider-config", options);
}

export function saveProviderConfig(draft: ProviderConfigDraft): Promise<ProviderConfigResponse> {
  return postJson<ProviderConfigResponse>("/api/provider-config", draft);
}

export function providerConfigResponseFromError(error: unknown): ProviderConfigResponse | null {
  if (!(error instanceof ApiError)) {
    return null;
  }
  if (!isRecord(error.payload)) {
    return null;
  }
  if (!isProviderConfigResponse(error.payload)) {
    return null;
  }
  return error.payload;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function isProviderConfigResponse(value: unknown): value is ProviderConfigResponse {
  if (!isRecord(value)) {
    return false;
  }
  if (!("validation" in value) || !isProviderValidationReport(value.validation)) {
    return false;
  }
  if ("saved" in value && typeof value.saved !== "boolean") {
    return false;
  }
  if ("error" in value && !isProviderConfigError(value.error)) {
    return false;
  }
  return true;
}

function isProviderValidationReport(value: unknown): value is ProviderValidationReport {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.passed === "boolean" &&
    Array.isArray(value.results) &&
    value.results.every(isProviderValidationResult)
  );
}

function isProviderValidationResult(value: unknown): value is ProviderValidationResult {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.kind === "string" &&
    typeof value.label === "string" &&
    typeof value.status === "string" &&
    typeof value.message === "string"
  );
}

function isProviderConfigError(value: unknown) {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.code === "string" &&
    typeof value.message === "string" &&
    isRecord(value.details)
  );
}
