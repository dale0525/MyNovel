import { ApiError, postJson } from "@/lib/api";
import type { ProviderConfigDraft, ProviderConfigResponse } from "./providerConfigTypes";

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
  return error.payload as ProviderConfigResponse;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}
