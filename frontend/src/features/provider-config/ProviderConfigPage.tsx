import { useEffect, useId, useState } from "react";

import {
  getProviderConfig,
  providerConfigResponseFromError,
  saveProviderConfig,
} from "./providerConfigApi";
import type {
  ProviderConfigDraft,
  ProviderConfigSummary,
  ProviderValidationReport,
  ProviderValidationResult,
} from "./providerConfigTypes";

type ProviderConfigPageProps = {
  bootstrapMessage?: string | null;
  loadExistingConfig?: boolean;
};

const emptyDraft: ProviderConfigDraft = {
  llmBaseUrl: "",
  llmApiKey: "",
  llmModel: "",
  embeddingUseLlmCredentials: true,
  embeddingBaseUrl: "",
  embeddingApiKey: "",
  embeddingModel: "",
};

export function ProviderConfigPage({
  bootstrapMessage,
  loadExistingConfig = false,
}: ProviderConfigPageProps) {
  const [draft, setDraft] = useState<ProviderConfigDraft>(emptyDraft);
  const [savedConfig, setSavedConfig] = useState<ProviderConfigSummary | null>(null);
  const [validation, setValidation] = useState<ProviderValidationReport | null>(null);
  const [message, setMessage] = useState<string | null>(bootstrapMessage ?? null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [canContinueAfterSave, setCanContinueAfterSave] = useState(false);
  const hasReusableLlmApiKey =
    savedConfig?.hasLlmApiKey === true &&
    sameEndpoint(draft.llmBaseUrl, savedConfig.llmBaseUrl);
  const hasReusableEmbeddingApiKey =
    !draft.embeddingUseLlmCredentials &&
    savedConfig?.embeddingUseLlmCredentials === false &&
    savedConfig.hasEmbeddingApiKey &&
    sameEndpoint(draft.embeddingBaseUrl, savedConfig.embeddingBaseUrl);
  const embeddingCredentialsRequired =
    !draft.embeddingUseLlmCredentials &&
    draft.embeddingModel.trim().length > 0 &&
    !hasReusableEmbeddingApiKey;

  useEffect(() => {
    if (!loadExistingConfig) {
      return;
    }

    const controller = new AbortController();
    getProviderConfig({ signal: controller.signal })
      .then((response) => {
        setSavedConfig(response.providerConfig);
        if (response.providerConfig) {
          setDraft(draftFromProviderConfig(response.providerConfig));
        }
      })
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        setMessage(error instanceof Error ? error.message : "已保存模型配置加载失败。");
      });

    return () => {
      controller.abort();
    };
  }, [loadExistingConfig]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage(null);
    setValidation(null);
    setCanContinueAfterSave(false);

    try {
      const response = await saveProviderConfig(sanitizeProviderConfigDraft(draft));
      setValidation(response.validation ?? null);
      if (hasFailedOptionalValidation(response.validation)) {
        setMessage("配置已保存，但 Embedding 连接未通过；章节将使用本地检索。");
        setCanContinueAfterSave(true);
        return;
      }
      window.location.href = "/";
    } catch (error) {
      const response = providerConfigResponseFromError(error);
      if (response?.validation) {
        setValidation(response.validation);
        setMessage(response.error?.message ?? "模型连接测试未全部通过。");
      } else {
        setMessage(error instanceof Error ? error.message : "配置保存失败。");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="provider-config-card" onSubmit={handleSubmit}>
      <div className="provider-config-card__intro">
        <p className="eyebrow">Provider setup</p>
        <h1>连接你的 AI 模型</h1>
        <p className="lede">
          填入 OpenAI-compatible 对话模型信息；Embedding 可作为章节历史召回增强能力。
        </p>
      </div>

      {message ? (
        <p aria-live="assertive" className="setup-message" role="alert">
          {message}
        </p>
      ) : null}

      <div className="provider-form-grid">
        <TextField
          label="Base url"
          value={draft.llmBaseUrl}
          onChange={(value) => updateDraft("llmBaseUrl", value)}
          placeholder="https://api.example.com/v1"
          required
        />
        <TextField
          label="API key"
          value={draft.llmApiKey}
          onChange={(value) => updateDraft("llmApiKey", value)}
          autoComplete="off"
          placeholder={hasReusableLlmApiKey ? "已保存，留空则继续使用" : undefined}
          type="password"
          required={!hasReusableLlmApiKey}
        />
        <TextField
          label="Model name"
          value={draft.llmModel}
          onChange={(value) => updateDraft("llmModel", value)}
          placeholder="gpt-4.1"
          required
        />
      </div>

      <section className="provider-model-section" aria-labelledby="embedding-section-title">
        <div>
          <h2 id="embedding-section-title">Embedding</h2>
          <label className="provider-checkbox">
            <input
              checked={draft.embeddingUseLlmCredentials}
              onChange={(event) =>
                updateDraft("embeddingUseLlmCredentials", event.target.checked)
              }
              type="checkbox"
            />
            <span>Embedding 使用 LLM 的 base url 和 api key</span>
          </label>
        </div>
        <TextField
          label="Embedding model name"
          value={draft.embeddingModel}
          onChange={(value) => updateDraft("embeddingModel", value)}
          hint="可选，不填时使用本地检索"
          placeholder="text-embedding-3-large"
        />
        {!draft.embeddingUseLlmCredentials ? (
          <div className="provider-form-grid">
            <TextField
              label="Embedding base url"
              value={draft.embeddingBaseUrl}
              onChange={(value) => updateDraft("embeddingBaseUrl", value)}
              placeholder="https://api.example.com/v1"
              required={embeddingCredentialsRequired}
            />
            <TextField
              label="Embedding API key"
              value={draft.embeddingApiKey}
              onChange={(value) => updateDraft("embeddingApiKey", value)}
              autoComplete="off"
              placeholder={hasReusableEmbeddingApiKey ? "已保存，留空则继续使用" : undefined}
              type="password"
              required={embeddingCredentialsRequired}
            />
          </div>
        ) : null}
      </section>

      {validation ? <ValidationResults draft={draft} validation={validation} /> : null}

      <button className="provider-submit-button" disabled={isSubmitting} type="submit">
        {isSubmitting ? "正在测试..." : "测试并保存配置"}
      </button>
      {canContinueAfterSave ? (
        <button
          className="provider-submit-button"
          onClick={() => {
            window.location.href = "/";
          }}
          type="button"
        >
          进入工作台
        </button>
      ) : null}
    </form>
  );

  function updateDraft<Key extends keyof ProviderConfigDraft>(
    key: Key,
    value: ProviderConfigDraft[Key],
  ) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
}

type TextFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  hint?: string;
  placeholder?: string;
  required?: boolean;
  type?: "text" | "password";
};

function TextField({
  label,
  value,
  onChange,
  autoComplete,
  hint,
  placeholder,
  required,
  type = "text",
}: TextFieldProps) {
  const inputId = useId();
  const hintId = hint ? `${inputId}-hint` : undefined;

  return (
    <div className="provider-field">
      <label htmlFor={inputId}>{label}</label>
      <input
        aria-describedby={hintId}
        autoComplete={autoComplete}
        id={inputId}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        type={type}
        value={value}
      />
      {hint ? (
        <span className="provider-field__hint" id={hintId}>
          {hint}
        </span>
      ) : null}
    </div>
  );
}

type ValidationResultsProps = {
  draft: ProviderConfigDraft;
  validation: ProviderValidationReport;
};

function ValidationResults({ draft, validation }: ValidationResultsProps) {
  return (
    <section
      aria-labelledby="validation-results-title"
      aria-live="polite"
      className="validation-results"
    >
      <h2 id="validation-results-title">模型连接结果</h2>
      <ul>
        {validation.results.map((result) => (
          <ValidationResultItem
            draft={draft}
            key={`${result.kind}-${result.label}`}
            result={result}
          />
        ))}
      </ul>
    </section>
  );
}

type ValidationResultItemProps = {
  draft: ProviderConfigDraft;
  result: ProviderValidationResult;
};

function ValidationResultItem({ draft, result }: ValidationResultItemProps) {
  return (
    <li className={`validation-result validation-result--${result.status}`}>
      <div>
        <strong>{result.label}</strong>
        <span>{result.status}</span>
      </div>
      <p>{redactSecrets(result.message, draft)}</p>
    </li>
  );
}

function redactSecrets(message: string, draft: ProviderConfigDraft): string {
  return Array.from(new Set([draft.llmApiKey, draft.embeddingApiKey]))
    .filter((secret) => secret.trim().length > 0)
    .sort((secret, other) => other.length - secret.length)
    .reduce(
      (current, secret) => current.replaceAll(secret, "[redacted]"),
      message,
    );
}

function sanitizeProviderConfigDraft(draft: ProviderConfigDraft): ProviderConfigDraft {
  if (!draft.embeddingUseLlmCredentials) {
    return draft;
  }

  return { ...draft, embeddingBaseUrl: "", embeddingApiKey: "" };
}

function draftFromProviderConfig(config: ProviderConfigSummary): ProviderConfigDraft {
  return {
    llmBaseUrl: config.llmBaseUrl,
    llmApiKey: "",
    llmModel: config.llmModel,
    embeddingUseLlmCredentials: config.embeddingUseLlmCredentials,
    embeddingBaseUrl: config.embeddingBaseUrl,
    embeddingApiKey: "",
    embeddingModel: config.embeddingModel,
  };
}

function sameEndpoint(value: string | null | undefined, other: string | null | undefined): boolean {
  return (value ?? "").trim() === (other ?? "").trim();
}

function hasFailedOptionalValidation(validation?: ProviderValidationReport): boolean {
  return (
    validation?.results.some(
      (result) => result.kind !== "llm" && result.status === "failed",
    ) ?? false
  );
}
