# AI API Setup Validation Design

Date: 2026-05-15

## Background

The current model setup page collects OpenAI-compatible connection fields, but saving is a plain form submit. It does not prove that the chat, embedding, and rerank models can actually be called, and rerank is still presented as optional in parts of the setup flow.

This change covers the first UI step: the screen shown on first launch when AI API setup is missing, and the same screen opened from settings to modify the AI API.

## Goals

- Require these fields before continuing: base URL, API key, chat model name, embedding model name, and rerank model name.
- Keep embedding and rerank credentials defaulted to "same base URL and API key as chat".
- Let users uncheck reuse for embedding or rerank and provide dedicated base URL and API key for that model type.
- Automatically test all three model types before saving.
- Block saving and continuation if any of the three tests fail.
- On repeated saves, only retest model types that are failed, untested, or whose effective connection fields changed since a passing test.
- Show clear per-model status in the setup UI.

## Non-Goals

- Do not add support for non-OpenAI-compatible provider protocols.
- Do not build a separate settings subsystem.
- Do not add background polling or async job state for the setup checks.
- Do not store API keys outside the existing local database.

## UI Design

The `/provider-config` page remains the dedicated setup surface and becomes the source of truth for first launch and settings changes.

The main form is grouped into three model cards:

- Chat model: base URL, API key, model name.
- Embedding model: model name plus a checked-by-default "reuse chat endpoint and key" control. When unchecked, dedicated base URL and API key fields are visible and required.
- Rerank model: model name plus the same reuse control and dedicated fields.

The right rail shows a "connection checks" checklist with one row each for chat, embedding, and rerank. Each row can be untested, testing through form submit, passed, failed, or skipped because a previous passing check still matches the current effective configuration.

## Save And Validation Flow

On POST `/provider-config`:

1. Parse the form into `ProviderConfig`.
2. Compare each model type with any previously saved passing validation fingerprint.
3. Skip a model test only when the submitted effective base URL, API key, and model name match a previous passing fingerprint for that model type.
4. Run the required checks for all remaining model types.
5. If every model type is passed or skipped, save the provider config and validation metadata, then redirect with the existing success message.
6. If any model type fails, do not save the provider config. Render the setup page with the submitted form values, per-model status, and concise error text.

## Model Checks

All checks use the existing OpenAI-compatible HTTP client surface:

- Chat: `POST {base_url}/chat/completions` with a minimal user message.
- Embedding: `POST {base_url}/embeddings` with a short text input.
- Rerank: `POST {base_url}/rerank` with a short query and two documents.

Responses are considered successful when the HTTP call returns without raising.

## Persistence

Provider configuration stays in the existing `ProviderConfig` table. A new local validation metadata record stores one passing fingerprint per model type. The fingerprint is derived from the effective base URL, API key, and model name so key values are not stored again in plain form for skip decisions.

If validation fails, only validation metadata for passed model types may be updated. The submitted provider config itself is not saved until all required model types pass.

## Testing

Tests must cover:

- The setup page renders all required fields and marks rerank model as required.
- Embedding and rerank reuse chat credentials by default.
- Dedicated embedding and rerank credentials are parsed when reuse is unchecked.
- Validation failure renders the setup page and does not save provider config.
- A second save skips a previously passed unchanged model type and retests only failed model types.
- Changing any effective field for a previously passed model type forces a retest.
