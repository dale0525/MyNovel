# Embedding Retrieval Design

Date: 2026-05-16

## Background

MyNovel currently has provider fields and validation checks for chat, embedding, and rerank models. Only the chat model is used by production workflows. The local retrieval index stores token-count dictionaries in `VectorEntry.embedding`, and `search_book_context()` ranks entries with lexical overlap rather than model embeddings.

The first production use case for real embedding retrieval is chapter generation. Before drafting a chapter, the pipeline should recall relevant accepted chapter text and trusted-state history so the LLM can reuse prior facts, callbacks, and foreshadowing without depending only on the compact trusted-state summary.

Rerank will be removed as a product capability. The current model context budget is large enough for the LLM to judge a bounded set of recalled fragments directly, and requiring a separate rerank endpoint creates unnecessary setup friction and provider incompatibility.

## Goals

- Use the configured embedding model to index accepted chapter text and trusted-state snapshots.
- Use embedding similarity to retrieve relevant historical fragments while building a chapter context package.
- Add retrieved fragments to the LLM context used by chapter planning, drafting, auditing, and revision.
- Keep the trusted state as the highest-priority fact source; retrieved fragments are supplemental evidence.
- Remove rerank from required setup, validation, bootstrap gating, and visible product configuration.
- Preserve a fallback path so chapter generation can continue if embedding is unavailable or fails.

## Non-Goals

- Do not add a vector database service in this phase.
- Do not implement rerank, rerank fallback, or rerank UI.
- Do not make retrieval the source of truth for canon facts.
- Do not retrieve unlimited historical text into the prompt.
- Do not redesign the chapter pipeline UI in this phase.

## Product Behavior

The provider setup flow requires only the chat model to unlock the app. Embedding fields remain available as an optional retrieval capability. If embedding is configured and has passed validation, chapter production uses it automatically.

When embedding is not configured, has not passed validation, or fails at runtime, the chapter pipeline falls back to the existing lexical retrieval behavior. If fallback also produces no results, the chapter still runs with the structured trusted state and volume plan.

Rerank fields are no longer required and should not block setup. Existing saved rerank values may remain in old local databases, but the app should ignore them.

## Architecture

### Provider Readiness

Provider readiness is split by capability:

- `llmReady`: required for app bootstrap and all AI production workflows.
- `embeddingReady`: optional; enables model-based retrieval when true.

The existing combined `providerConfigured` bootstrap value should become true when `llmReady` is true. API responses can expose `embeddingReady` for settings and diagnostics, but no main workflow depends on it as a hard gate.

### Embedding Client

The existing OpenAI-compatible `/embeddings` client remains the integration surface. A small workflow-level embedding service should wrap it and provide:

- Single-text embedding for query generation.
- Batch embedding for rebuilds or future import flows when supported by the provider.
- Response parsing that accepts the standard OpenAI-compatible shape with `data[].embedding`.
- Clear errors when a provider response has no usable vector.

### Vector Storage

`VectorEntry.embedding` should store real numeric vectors when model embeddings are available. To avoid mixing old lexical dictionaries with new vectors, the metadata must identify the embedding kind and model:

- `metadata.embedding_kind = "model"` for numeric vectors.
- `metadata.embedding_model = <model name>`.
- `metadata.embedding_dimensions = <vector length>`.

Legacy lexical entries can still be read for fallback. New lexical fallback entries may keep using the existing token-count dictionary, but model similarity must only run against numeric vector lists from the same embedding model.

### Indexing

Accepted chapter approval remains the primary indexing point. When a chapter is approved, the pipeline already creates two entries:

- `accepted_chapter`: chapter title, summary, and final text.
- `trusted_state`: state changes and trusted-state snapshot content.

After this change, each entry attempts to store a model embedding. If the embedding call fails, the approval should not fail; the entry is stored with lexical fallback data and error metadata.

### Retrieval Query

Before building a chapter context package, the pipeline creates a retrieval query from:

- Chapter number and title.
- Chapter goal.
- `must_write` items.
- Relevant trusted-state summary fields such as characters, foreshadowing, and recent chapter summaries.

The query is embedded when `embeddingReady` is true. The retriever ranks model-indexed entries by cosine similarity and returns a bounded set of fragments.

Defaults:

- `top_k`: 10 fragments.
- Character budget: 10000 Chinese characters across all retrieved fragments.
- Prefer diversity by keeping at most a small number of entries per source type when scores are close.

The exact defaults can live as constants in the retrieval workflow so tests can assert deterministic behavior.

### Context Package

`chapter.context_package` gains a `retrieved_context` array. Each item contains:

- `source_type`
- `source_id`
- `score`
- `text`
- `metadata`

Prompt rendering should place retrieved context after trusted state and chapter plan. The prompt text must tell the LLM that trusted state overrides retrieved fragments when they disagree.

## Data Flow

1. User approves chapter N.
2. The pipeline updates trusted state.
3. The pipeline indexes accepted chapter text and trusted-state text.
4. Indexing attempts model embedding and stores numeric vectors when successful.
5. User starts chapter N+1.
6. The pipeline builds a retrieval query from the next chapter plan and trusted state.
7. The retriever performs embedding similarity search when possible, otherwise lexical fallback.
8. Retrieved fragments are added to `context_package.retrieved_context`.
9. The LLM receives trusted state, chapter plan, and retrieved fragments.

## Error Handling

- Embedding validation failure should not block app bootstrap.
- Runtime embedding failure should be recorded in retrieval metadata or run trace, then fall back to lexical retrieval.
- Dimension mismatch, missing vectors, or changed embedding model should exclude affected entries from model similarity and use fallback where possible.
- Empty retrieval results are valid and should not fail chapter generation.

## Migration

No destructive migration is required.

Existing `VectorEntry.embedding` values are treated as legacy lexical dictionaries. New model vectors can be written into the same JSON column as arrays of numbers. Retrieval code must inspect the value shape and metadata before deciding how to score an entry.

Saved rerank fields can remain in `ProviderConfig` for backward compatibility during this phase. Product logic should stop requiring or checking them. A later cleanup can remove columns and UI remnants once the new setup flow is stable.

## Testing

Backend tests should cover:

- Provider validation passes and unlocks bootstrap with only a valid chat model.
- Embedding validation status is reported independently from chat readiness.
- Rerank missing or failing no longer blocks saving provider config.
- Accepted chapter indexing stores numeric vectors when embedding succeeds.
- Indexing falls back without failing chapter approval when embedding fails.
- Model retrieval ranks entries by vector similarity and respects `top_k` and character budget.
- Retrieval ignores vectors from a different embedding model.
- Chapter context package includes `retrieved_context` before LLM calls.
- Prompt rendering states that trusted state has priority over retrieved fragments.

Frontend tests should cover:

- Setup no longer requires rerank fields.
- The app can bootstrap when chat is validated and embedding is unavailable.
- Settings can show embedding as optional retrieval enhancement without presenting rerank as required.

## Acceptance Criteria

- A user with only a working chat model can enter the app and create a book.
- A user with chat plus embedding gets model-based historical retrieval in chapter production.
- Rerank is no longer a blocker anywhere in setup or production.
- Chapter approval and chapter generation remain robust when embedding calls fail.
- Retrieved context is bounded, source-labeled, and subordinate to trusted state.
