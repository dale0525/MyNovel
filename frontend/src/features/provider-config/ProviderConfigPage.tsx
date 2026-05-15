import { useState } from "react";

import {
  providerConfigResponseFromError,
  saveProviderConfig,
} from "./providerConfigApi";
import type {
  ProviderConfigDraft,
  ProviderValidationReport,
  ProviderValidationResult,
} from "./providerConfigTypes";

type ProviderConfigPageProps = {
  bootstrapMessage?: string | null;
};

const emptyDraft: ProviderConfigDraft = {
  llmBaseUrl: "",
  llmApiKey: "",
  llmModel: "",
  embeddingUseLlmCredentials: true,
  embeddingBaseUrl: "",
  embeddingApiKey: "",
  embeddingModel: "",
  rerankUseLlmCredentials: true,
  rerankBaseUrl: "",
  rerankApiKey: "",
  rerankModel: "",
};

export function ProviderConfigPage({ bootstrapMessage }: ProviderConfigPageProps) {
  const [draft, setDraft] = useState<ProviderConfigDraft>(emptyDraft);
  const [validation, setValidation] = useState<ProviderValidationReport | null>(null);
  const [message, setMessage] = useState<string | null>(bootstrapMessage ?? null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage(null);

    try {
      const response = await saveProviderConfig(draft);
      setValidation(response.validation ?? null);
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
          填入 OpenAI-compatible 服务信息，保存前会分别测试 LLM、Embedding 和
          Rerank 模型。
        </p>
      </div>

      {message ? <p className="setup-message">{message}</p> : null}

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
          type="password"
          required
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
          placeholder="text-embedding-3-large"
          required
        />
        {!draft.embeddingUseLlmCredentials ? (
          <div className="provider-form-grid">
            <TextField
              label="Embedding base url"
              value={draft.embeddingBaseUrl}
              onChange={(value) => updateDraft("embeddingBaseUrl", value)}
              placeholder="https://api.example.com/v1"
              required
            />
            <TextField
              label="Embedding API key"
              value={draft.embeddingApiKey}
              onChange={(value) => updateDraft("embeddingApiKey", value)}
              type="password"
              required
            />
          </div>
        ) : null}
      </section>

      <section className="provider-model-section" aria-labelledby="rerank-section-title">
        <div>
          <h2 id="rerank-section-title">Rerank</h2>
          <label className="provider-checkbox">
            <input
              checked={draft.rerankUseLlmCredentials}
              onChange={(event) => updateDraft("rerankUseLlmCredentials", event.target.checked)}
              type="checkbox"
            />
            <span>Rerank 使用 LLM 的 base url 和 api key</span>
          </label>
        </div>
        <TextField
          label="Rerank model name"
          value={draft.rerankModel}
          onChange={(value) => updateDraft("rerankModel", value)}
          placeholder="rerank-v3"
          required
        />
        {!draft.rerankUseLlmCredentials ? (
          <div className="provider-form-grid">
            <TextField
              label="Rerank base url"
              value={draft.rerankBaseUrl}
              onChange={(value) => updateDraft("rerankBaseUrl", value)}
              placeholder="https://api.example.com/v1"
              required
            />
            <TextField
              label="Rerank API key"
              value={draft.rerankApiKey}
              onChange={(value) => updateDraft("rerankApiKey", value)}
              type="password"
              required
            />
          </div>
        ) : null}
      </section>

      {validation ? <ValidationResults draft={draft} validation={validation} /> : null}

      <button className="provider-submit-button" disabled={isSubmitting} type="submit">
        {isSubmitting ? "正在测试..." : "测试并保存配置"}
      </button>
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
  placeholder?: string;
  required?: boolean;
  type?: "text" | "password";
};

function TextField({
  label,
  value,
  onChange,
  placeholder,
  required,
  type = "text",
}: TextFieldProps) {
  return (
    <label className="provider-field">
      <span>{label}</span>
      <input
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        type={type}
        value={value}
      />
    </label>
  );
}

type ValidationResultsProps = {
  draft: ProviderConfigDraft;
  validation: ProviderValidationReport;
};

function ValidationResults({ draft, validation }: ValidationResultsProps) {
  return (
    <section className="validation-results" aria-labelledby="validation-results-title">
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
  return [draft.llmApiKey, draft.embeddingApiKey, draft.rerankApiKey]
    .filter((secret) => secret.trim().length > 0)
    .reduce(
      (current, secret) => current.replaceAll(secret, "[redacted]"),
      message,
    );
}
