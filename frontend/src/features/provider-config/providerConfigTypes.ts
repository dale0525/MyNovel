export type ProviderConfigDraft = {
  llmBaseUrl: string;
  llmApiKey: string;
  llmModel: string;
  embeddingUseLlmCredentials: boolean;
  embeddingBaseUrl: string;
  embeddingApiKey: string;
  embeddingModel: string;
};

export type ProviderValidationStatus = "passed" | "failed" | "skipped" | string;

export type ProviderValidationResult = {
  kind: "llm" | "embedding" | "rerank" | string;
  label: string;
  status: ProviderValidationStatus;
  message: string;
};

export type ProviderValidationReport = {
  passed: boolean;
  results: ProviderValidationResult[];
};

export type ProviderConfigSummary = {
  llmBaseUrl: string;
  llmModel: string;
  hasLlmApiKey: boolean;
  embeddingUseLlmCredentials: boolean;
  embeddingBaseUrl: string;
  embeddingModel: string;
  hasEmbeddingApiKey: boolean;
  rerankUseLlmCredentials: boolean;
  rerankBaseUrl: string | null;
  rerankModel: string | null;
  hasRerankApiKey: boolean;
};

export type ProviderConfigResponse = {
  saved?: boolean;
  embeddingValidated?: boolean;
  providerConfig?: ProviderConfigSummary | null;
  validation?: ProviderValidationReport;
  error?: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
};
